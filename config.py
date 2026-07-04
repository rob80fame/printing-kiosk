import os
import json

with open('config.json', 'r') as f:
    file = json.load(f)

#Password set during postgresql configuration
db_pass = file['pass']

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

npm_dir = file['npmdir']

#Name of the istance on evolution-api
instance_name = file['name']

phonenum = file['phonenum']
#Phonenumber 
remoteJidAlt = f"{phonenum}@s.whatsapp.net"

#Api key set in .env
apikey = file['apikey']

#Path to project
Proj_path = os.getcwd()

#Docpath
Doc_path = os.path.join(Proj_path, "DOCUMENTS")
#Imgpath
Img_path = os.path.join(Proj_path, "IMAGES")

#Printer name
PRINTER = file['Printer']

##ADMIN PASS
sudo = file['sudo']