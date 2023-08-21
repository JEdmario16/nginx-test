from flask import Flask, jsonify, request
from redis import Redis

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import random
import os
import time
import json

db_user = os.environ.get("POSTGRES_USER")
db_password = os.environ.get("POSTGRES_PASSWORD")
db_host = "db" # Nome do serviço que criamos no docker-compose.yml
db_port = os.environ.get("POSTGRES_PORT", 5432)
db_name = os.environ.get("DB_NAME", "postgres")

engine = create_engine(f"postgresql+pg8000://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

Base = declarative_base()

# criando uma sessão para o banco de dados
Session = sessionmaker(bind=engine)

# criando o modelo da tabela books
class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    author = Column(String)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
        }
    
    def __repr__(self):
        return "<Book(title='%s', author='%s')>" % (self.title, self.author)
    


# criando a tabela books
Base.metadata.create_all(bind=engine)

app = Flask(__name__)

# Note que estamos passando o nome do serviço que criamos no docker-compose.yml
# como host e a porta que o serviço está rodando
redis = Redis(host="redis", port="6379")


@app.route("/")
def index():
    return {
        "message": "Hello World",
    }

@app.route("/outra_page")
def outra_page():
    return {"message": "Esta é uma outra página e está funcionando =)"}

@app.route("/redis")
def redis_test():
    request_time = time.time()

    # flag para verificar se o valor que estamos vendo é um valor salvo no redis(ou seja, um cache)
    is_a_cache_value = False

    # salva um número aleatório no redis, caso não exista um valor salvo
    # com um tempo de expiração de 10 segundos

    if not redis.get("number"):
        # para mostrar o funcionamento do redis, irei adicionar um delay de 10 segundos
        # Pense nisso como uma operação que demora 10 segundos para ser executada, como uma consulta ao banco de dados
        time.sleep(10)
        redis.set("number", random.randint(0, 100), ex=10)

    # caso o valor já exista no redis, então é um valor salvo no cache
    else:
        is_a_cache_value = True

    # retorna o valor salvo no redis
    return {
        "number": float(
            redis.get("number")
        ),  # o redis retorna um valor do tipo bytes, então precisamos converter para float
        "eleapsed_time": time.time() - request_time,
        "is_a_cache_value": is_a_cache_value,
    }

@app.route("/create_book", methods=["POST", "GET"])
def create_book():

    if request.method == "GET":

        return """<form method='POST'>
                    <label for='title'>Título</label>
                    <input type='text' name='title'>
                    <label for='author'>Autor</label>
                    <input type='text' name='author'>
                    <input type='submit'>
                </form"""
    title = request.form.get("title", 'Harry Potter')
    author = request.form.get("author", 'J.K. Rowling')
    # cria um novo livro
    new_book = Book(title=title, author=author)
    # salva o livro no banco de dados
    with Session() as session:
        session.add(new_book)
        session.commit()
    
    return {"message": "Livro criado com sucesso"}

@app.route("/get_books", methods=["GET"])
def get_books():
    # retorna todos os livros salvos no banco de dados
    with Session() as session:
        books = session.query(Book).all()
    
    books = [book.to_dict() for book in books]
    return {"books": books}


@app.route("/get_book_by_id/<int:id>", methods=["GET"])
def get_book_by_id(id):
    id = int(id)
    # Checa se o livro está salvo no cache
    if redis.hgetall(f"book_{id}"):
        # retorna o livro salvo no cache
        book = redis.hgetall(f"book_{id}")
        book = {key.decode("utf-8"): value.decode("utf-8") for key, value in book.items()}
        return {"book": book, "is_a_cache_value": True}

    # caso o livro não esteja salvo no cache, então ele é buscado no banco de dados
    with Session() as session:
        book = session.query(Book).filter_by(id=id).first()
    
    if book:
        # salva o livro no cache
        redis.hset(f"book_{id}", mapping=book.to_dict())

        return {"book": book.to_dict(), "is_a_cache_value": False}
    
    return {"message": "Livro não encontrado"}