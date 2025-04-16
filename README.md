# 🛒 Subasta en Tiempo Real con FastAPI y AWS

Este proyecto implementa una **API REST** para gestionar subastas en tiempo real utilizando **Python** y **FastAPI**, desplegado como función **AWS Lambda** y expuesto mediante **API Gateway**. Se utiliza **DynamoDB** para almacenar ítems y pujas, **SQS** para eventos, y **SNS** para notificaciones por correo electrónico a los usuarios participantes.

---

## ⚙️ Infraestructura y Servicios Utilizados

- **FastAPI** (framework web)
- **AWS Lambda** (serverless backend)
- **API Gateway** (exposición HTTP)
- **DynamoDB** (base de datos NoSQL)
- **SQS** (cola para eventos de pujas)
- **SNS** (notificaciones por correo a usuarios)
- **Terraform** (infraestructura como código)

---

## 📦 Requisitos

- Python 3.9 o superior (preferiblemente 3.9 para Lambda)
- Terraform ≥ 1.0
- AWS CLI configurado con credenciales válidas
- Archivo `function_lambda.zip` con el código de la API empaquetado

---

## 🐍 Configuración del entorno virtual

1. Crea un entorno virtual:

python -m venv venv

2. Activa el entorno virtual:

- En Windows:
venv\Scripts\activate

- En macOS/Linux:
source venv/bin/activate

3. Instala las dependencias necesarias:

pip install -r requirements.txt

---

## 📦 Empaquetar el proyecto para Lambda

1. Instala las dependencias necesarias en una carpeta llamada package/:
pip install -r requirements.txt -t package/

2. Copia el contenido del proyecto (carpeta app/, lambda_function.py, etc.) dentro de package/:
cp -r app lambda_function.py package/

3. Desde la carpeta package/, crea el archivo ZIP:

cd package
zip -r ../function_lambda.zip .
cd ..

✅ El archivo function_lambda.zip quedará en la raíz del proyecto, listo para ser cargado al bucket de S3 mediante Terraform.

---

##  Ejecución de pruebas unitarias

- ejecuta pytest -v para ejecutar las pruebas unitarias del codigo

## 🚀 Despliegue de la Infraestructura con Terraform

1. Clona este repositorio y navega al directorio `infra/terraform`:

cd infra/terraform

2. En el archivo terraform.tfvars coloca tus variables personales:

- aws_access_key = "TU_ACCESS_KEY"
- aws_secret_key = "TU_SECRET_KEY"
- aws_region     = "us-east-1"

3. Inicializa y despliega la infraestructura:
terraform init
terraform apply

✅ Esto creará:

- Función Lambda
- API Gateway
- Tablas DynamoDB
- Topic SNS (para notificaciones)
- Cola SQS
- Permisos IAM asociados

---

🌐 Endpoints de la API
La API quedará disponible en un endpoint de API Gateway similar a:
https://<API-ID>.execute-api.us-east-1.amazonaws.com/prod

1. Crear ítem de subasta

- POST /items
{
  "name": "PlayStation 5",
  "start_price": 100.0,
  "duration_minutes": 5
}

2. Realizar una puja (bid)

- POST /bids
{
  "item_id": "ID_DEL_ITEM",
  "user_email": "usuario@email.com",
  "amount": 120.0
}

🔔 Este endpoint crea o reutiliza un SNS Topic asociado a la subasta y suscribe el correo del usuario ganador y perdedor. El correo recibirá un enlace para confirmar la suscripción a ese topic para todos los usuarios participantes.

3. Consultar resultado de la subasta

- GET /items/{item_id}

**Ejemplo: GET /items/10fa2555-d238-4b47-8227-5a0cf5101579**

🔚 Una vez finalizada la subasta (según el tiempo establecido), se enviará una notificación al correo del usuario ganador y a los participantes, solo si previamente confirmaron su suscripción al topic.

---

## 📩 Lógica de Suscripción y Notificación SNS
En la primera puja de un usuario en una subasta, se lo suscribe al topic auction-result-{item_id}.

El usuario debe confirmar vía correo electrónico su suscripción (enlace de confirmación).

Al finalizar la subasta, solo los correos confirmados recibirán un mensaje indicando si ganaron o no.

---

## 🧠 Autor
Desarrollado por Hugo Bustamante como parte de una prueba técnica.
Incluye buenas prácticas en backend moderno, además de despliegue serverless sobre AWS con Terraform.