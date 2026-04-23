import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

'''os → ler variáveis do sistema
load_dotenv → carrega o .env
create_engine → cria ligação à base
sessionmaker → cria sessões
DeclarativeBase → base para modelos'''

load_dotenv()#carrega o ficheiro .env para o Python
DATABASE_URL = os.getenv("DATABASE_URL")#lê a variável DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não encontrada no .env")#se não existir, o programa para Isso evita bugs silenciosos.


engine = create_engine(DATABASE_URL)#cria a ligação com a base de dados    

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)#isso cria sessões

class Base(DeclarativeBase):#essa classe será a base de todas as tabelas
    pass

