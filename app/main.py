# 1. iris_model.joblib 옮기기
# 2. mlflow로 언제나 prod의 @champion 모델 가리키도록 관리
# pip install mlflow
# mlflow ui
from fastapi import FastAPI, HTTPException, Depends, Request, Form
# jinja 형식으로 작성된 html 파일을 렌더링해주기 위한 모듈
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import joblib
import numpy as np
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import logging
from models import Base, IrisPrediction  # ORM 모델 가져오기
from fastapi.staticfiles import StaticFiles # 정적파일 경로 관리
# import mlflow
import logging
# 로깅 기본 설정
# 1. 포맷터 정의: 로그 메시지 포맷을 지정
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 2. 콘솔 핸들러: 콘솔(터미널)에 로그 출력
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO) # INFO 레벨 이상만 출력

# 3. 파일 핸들러: 파일에 로그 기록
file_handler = logging.FileHandler('./fastapi_app.log', encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO) # 로그파일을 사용하려는 목적에 따라 

# 4. 로거 객체 생성 및 핸들러 추가
logger = logging.getLogger(__name__) # 어느 파일에서 로그가 발생했는지
logger.setLevel(logging.DEBUG) # 로거의 최소 레벨 설정 (DEBUG 레벨부터 모두 처리)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 로깅 설정
logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# 환경 변수 로드
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')

# 머신러닝 모델 로드
model = joblib.load("iris_model.joblib")

# # 모델 로드 - mlflow의 uri를 맨 위에 작성
# mlflow.set_tracking_uri("http://host.docker.internal:5000")
# mlflow.set_tracking_uri("http://localhost:5001")

# prod_model_uri = 'models:/iris-classification-prod@champion'
# model = mlflow.sklearn.load_model(prod_model_uri)
# model = mlflow.pyfunc.load_model(prod_model_uri)


# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI()

##################  정적인 파일들을 관리하는 별도의 폴더에 대한 정보 작성
app.mount('/static', StaticFiles(directory='static'), name='static')

# 데이터베이스 연결 설정
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

# 템플릿 경로 선언
templates = Jinja2Templates(directory="templates")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 테이블 생성
Base.metadata.create_all(bind=engine)

# 입력 데이터 스키마 정의
class IrisInput(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

# 데이터베이스 세션 종속성 정의
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 사용자가 값을 입력하는 화면에 대한 엔드포인트
@app.get("/")
def read_form(request:Request):
    client_host = request.client.host # client의 ip 주소 
    endpoint_path = request.url.path
    logger.info(f"user in - client_host: {client_host} / endpoint_path {endpoint_path} ")
    return templates.TemplateResponse(request=request, name="input_form.html")

# 사용자가 값을 입력하고, 추론의 결과를 어떻게 받았는지 상태를 가장 추적하기 좋은 위치들에 INFO 레벨의 로그를 찍어보세요.
# 예측 및 데이터베이스 저장 엔드포인트 정의
@app.post("/predict")
def predict(request: Request,     
            sepal_length: float = Form(...), # elipsis : Form() , Query(), Path()처럼 입력값에 ...을 작성해 두면 필수요소로 여김 - ...으로 required를 약속처럼 채워넣습니다.
            sepal_width: float = Form(...),
            petal_length: float = Form(...),
            petal_width: float = Form(...),
            db: Session = Depends(get_db)):
    try:
        client_host = request.client.host # client의 ip 주소 
        endpoint_path = request.url.path
        logger.info(f"user prediction - client_host: {client_host} / endpoint_path {endpoint_path} / data: [sepal_length: {sepal_length} / sepal_width: {sepal_width} / petal_length: {petal_length} / petal_width: {petal_width}]")
        features = np.array([[sepal_length, sepal_width,
                petal_length, petal_width]])
        prediction = model.predict(features)
        prediction = int(prediction[0]) 
        new_pred = IrisPrediction(
            sepal_length=sepal_length, 
            sepal_width=sepal_width,
            petal_length=petal_length, 
            petal_width=petal_width,
            prediction=prediction
        )

        db.add(new_pred)
        db.commit()
        db.refresh(new_pred)
        
        # 전체 DB 기록 가져오기
        all_predictions = db.query(IrisPrediction).all()
        
        logger.info(f"model predicted - - client_host: {client_host} / endpoint_path {endpoint_path} / data: [sepal_length: {sepal_length} / sepal_width: {sepal_width} / petal_length: {petal_length} / petal_width: {petal_width} / prediction: {prediction}]")
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                'sepal_length': sepal_length,
                "sepal_width": sepal_width,
                "petal_length": petal_length, 
                "petal_width": petal_width, 
                "prediction": prediction,
                "history": all_predictions
            }
        ) # json 객체로 전달할 수 있게 기본 자료형으로 변환
    except Exception as e: # e를 받아서 에러메시지를 함께 확인 가능
        logger.warning(f"server error - {e} - sepal_length: {sepal_length} / sepal_width: {sepal_width} / petal_length: {petal_length} / petal_width: {petal_width} / prediction: {prediction}")
        raise HTTPException(500, "server error")
