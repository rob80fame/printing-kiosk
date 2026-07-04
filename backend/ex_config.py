import os

#Password set during postgresql configuration
db_pass = ""

DB_CONFIG = {
    "dbname": "images",
    "user": "postgres",
    "password": db_pass,
    "host": "localhost",
    "port": "5432"
}

#Name of the istance on evolution-api
instance_name = ""
#Api key set in .env
apikey = ""

#Path to project
Proj_path = r""

#Docpath
Doc_path = os.path.join(Proj_path, "backend", "DOCUMENTS")
#Imgpath
Img_path = os.path.join(Proj_path, "backend", "IMAGES")