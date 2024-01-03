from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime
import json

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    sender_id = Column(String)
    message = Column(String)
    timestamp = Column(DateTime)
    additional_info = Column(Text)

    def set_additional_info(self, info_dict):

        self.additional_info = json.dumps(info_dict)

    def get_additional_info(self):

        return json.loads(self.additional_info) if self.additional_info else None

class ChatStorage:
    def __init__(self, db_path):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_message(self, sender_id, message, additional_info=None):
        try:
            with self.Session() as session:
                new_message = Message(sender_id=sender_id, message=message, timestamp=datetime.now())
                if additional_info is not None:
                    new_message.set_additional_info(additional_info)
                session.add(new_message)
                session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao adicionar mensagem: {e}")
            raise

    def remove_message(self, message_id):
        try:
            with self.Session() as session:
                message = session.query(Message).filter(Message.id == message_id).first()
                if message:
                    session.delete(message)
                    session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao remover mensagem: {e}")
            raise

    def get_messages(self):
        try:
            with self.Session() as session:
                return session.query(Message).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter mensagens: {e}")
            raise

    def create_custom_table_from_df(self, df, table_name):
        try:
            if not df.columns.is_unique:
                raise ValueError("As colunas do DataFrame devem ser únicas.")
            columns = [Column(str(column), String) for column in df.columns]
            custom_table = Table(table_name, Base.metadata, *columns, Column('id', Integer, primary_key=True))
            custom_table.create(self.engine)
        except SQLAlchemyError as e:
            logger.error(f"Erro ao criar tabela customizada: {e}")
            raise
        except ValueError as e:
            logger.error(f"Erro de validação: {e}")
            raise
