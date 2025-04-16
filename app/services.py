import uuid
from app.aws_clients import sqs, sns, SQS_QUEUE_URL, SNS_TOPIC_ARN
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.database import items_table, bids_table
from app.models import Item, Bid
from app.schemas import ItemCreate, BidCreate
from decimal import Decimal

def create_item(item_data: ItemCreate):
    item_id = str(uuid.uuid4())
    end_time = (datetime.utcnow() + timedelta(minutes=int(item_data.duration_minutes))).isoformat()

    print(f"start_price type: {type(item_data.start_price)}, value: {item_data.start_price}")
    print(f"duration_minutes type: {type(item_data.duration_minutes)}, value: {item_data.duration_minutes}")
    
    item = Item(
        id=item_id,
        name=item_data.name,
        start_price=Decimal(str(item_data.start_price)),   
        end_time=end_time,
        highest_bid=Decimal("0.0")
    )

    try:
        item_dict = item.dict()
        print("Item dict antes de guardar en DynamoDB:", item.dict())
        print(type(item_dict["start_price"]))
        items_table.put_item(Item=item_dict)
    except Exception as e:
        print("Error al guardar en DynamoDB:", str(e))
        raise HTTPException(status_code=500, detail="Error al guardar el item")
    return item

def place_bid(bid_data: BidCreate):
    item = items_table.get_item(Key={"id": bid_data.item_id}).get("Item")

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if datetime.utcnow() > datetime.fromisoformat(item["end_time"]):
        raise HTTPException(status_code=403, detail="Auction has ended")

    if Decimal(str(bid_data.amount)) <= Decimal(str(item.get("highest_bid", 0.0))):
        raise HTTPException(status_code=400, detail="Bid must be higher than current highest bid")

    bid = Bid(
        item_id=bid_data.item_id,
        user_email=bid_data.user_email,
        amount=Decimal(str(bid_data.amount)),
    )

    # Crear o reutilizar el topic SNS para esta subasta
    topic_name = f"auction-result-{bid_data.item_id}"
    try:
        topic_response = sns.create_topic(Name=topic_name)
        topic_arn = topic_response["TopicArn"]
    except Exception as e:
        print(f"Error creando topic SNS: {str(e)}")
        topic_arn = None  # para evitar crash si falla

    # Verificar si el usuario ya está suscrito
    if topic_arn:
        try:
            subscriptions = sns.list_subscriptions_by_topic(TopicArn=topic_arn)["Subscriptions"]
            already_subscribed = any(sub["Endpoint"] == bid_data.user_email for sub in subscriptions)

            if not already_subscribed:
                sns.subscribe(
                    TopicArn=topic_arn,
                    Protocol="email",
                    Endpoint=bid_data.user_email
                )
                print(f"Usuario {bid_data.user_email} suscrito al topic {topic_arn}")
        except Exception as e:
            print(f"Error verificando/subscribiendo al SNS: {str(e)}")

    # Guardar puja en DynamoDB
    bids_table.put_item(Item=bid.dict())

    # Actualizar item con puja más alta
    items_table.update_item(
        Key={"id": bid_data.item_id},
        UpdateExpression="SET highest_bid = :hb, highest_bidder = :hb_email",
        ExpressionAttributeValues={
            ":hb": Decimal(str(bid_data.amount)),
            ":hb_email": bid_data.user_email
        }
    )

    # Enviar evento a SQS
    try:
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=f"Puja registrada: {bid_data.user_email} ofreció {bid_data.amount} por el item {bid_data.item_id}"
        )
    except Exception as e:
        print(f"Error al enviar mensaje a SQS: {str(e)}")

    return bid


def get_auction_result(item_id: str):
    item = items_table.get_item(Key={"id": item_id}).get("Item")
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if datetime.utcnow() < datetime.fromisoformat(item["end_time"]):
        return {"status": "Auction is still ongoing"}

    winner_email = item.get("highest_bidder")
    winning_bid = item.get("highest_bid", 0)

    # Crear un SNS Topic (opcional, solo para organización)
    topic_name = f"auction-result-{item_id}"
    try:
        topic_response = sns.create_topic(Name=topic_name)
        topic_arn = topic_response['TopicArn']
    except Exception as e:
        print(f"Error creando el topic SNS: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creando SNS topic")
    
    # Obtener todas las suscripciones confirmadas
    confirmed_subs = []
    try:
        subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)["Subscriptions"]
        confirmed_subs = [sub for sub in subs if sub["SubscriptionArn"] != "PendingConfirmation"]
    except Exception as e:
        print(f"Error listando suscripciones: {str(e)}")

    # Obtener todos los correos de usuarios que participaron
    try:
        response = bids_table.query(
            KeyConditionExpression="item_id = :item_id",
            ExpressionAttributeValues={":item_id": item_id}
        )
        bids = response.get("Items", [])
        emails_sent = set()

        for bid in bids:
            email = bid["user_email"]
            if email in emails_sent:
                continue
            emails_sent.add(email)

            # Verificar si el correo está confirmado
            if not any(sub["Endpoint"] == email for sub in confirmed_subs):
                print(f"El usuario {email} no ha confirmado su suscripción. No se le envía el resultado.")
                continue

            if email == winner_email:
                message = f"¡Felicidades! Has ganado la subasta del ítem '{item['name']}' con una puja de {winning_bid}."
            else:
                message = f"Gracias por participar. El ítem '{item['name']}' fue ganado por {winner_email} con una puja de {winning_bid}."

            try:
                sns.publish(
                    TopicArn=topic_arn,
                    Message=message,
                    Subject="Resultado de Subasta"
                )
            except Exception as e:
                print(f"Error enviando mensaje a {email}: {str(e)}")

    except Exception as e:
        print(f"Error consultando pujas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener resultados")

    return {
        "status": "Auction ended",
        "winner": winner_email,
        "winning_bid": winning_bid
    }