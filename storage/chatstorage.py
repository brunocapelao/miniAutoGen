from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import pandas as pd

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    sender_id = Column(String)
    message = Column(String)
    timestamp = Column(DateTime)

class ChatStorage:
    def __init__(self, db_path):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_message(self, sender_id, message):
        session = self.Session()
        try:
            new_message = Message(sender_id=sender_id, message=message, timestamp=datetime.now())
            session.add(new_message)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erro ao adicionar mensagem: {e}")
            raise
        finally:
            session.close()

    def remove_message(self, message_id):
        session = self.Session()
        try:
            message = session.query(Message).filter(Message.id == message_id).first()
            if message:
                session.delete(message)
                session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erro ao remover mensagem: {e}")
            raise
        finally:
            session.close()

    def get_messages(self):
        session = self.Session()
        try:
            messages = session.query(Message).all()
            return messages
        except Exception as e:
            print(f"Erro ao obter mensagens: {e}")
            raise
        finally:
            session.close()

    def create_custom_table_from_df(self, df: pd.DataFrame, table_name: str):
        """
        Cria uma tabela personalizada com base nas colunas do DataFrame fornecido.

        Args:
            df (pd.DataFrame): DataFrame contendo as definições de colunas.
            table_name (str): Nome da tabela a ser criada.
        """
        columns = [Column(column, String) for column in df.columns]
        custom_table = Table(table_name, Base.metadata, *columns, Column('id', Integer, primary_key=True))
        custom_table.create(self.engine)