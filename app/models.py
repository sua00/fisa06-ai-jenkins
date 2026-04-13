from sqlalchemy import Column, Integer, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# SQLAlchemy 모델 정의 - 모델의 추론 결과를 함께 db에 적재 
class IrisPrediction(Base):
    __tablename__ = "iris_prediction"
    id = Column(Integer, primary_key=True, index=True)
    sepal_length = Column(Float)
    sepal_width = Column(Float)
    petal_length = Column(Float)
    petal_width = Column(Float)
    prediction = Column(Integer)