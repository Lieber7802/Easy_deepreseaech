import json
import logging
from typing import AsyncIterator
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import shutil

# 确保能找到 src 模块
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import ResearchRequest
from service import DeepResearchService
from src.core.rag_manager import get_rag_manager

load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Easy Deep Research")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/research/stream")
async def stream_research(payload: ResearchRequest):
    logger.info(f"Received research request: {payload.topic}")
    service = DeepResearchService()
    
    async def event_generator() -> AsyncIterator[str]:
        try:
            # 默认使用 tavily，如果 payload 指定了 search_api 则覆盖
            search_api = payload.search_api or "tavily"
            async for event in service.run_stream(payload.topic, search_api=search_api):
                logger.debug(f"Yielding event: {event['type']}")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Research failed")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        # Save file temporarily
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingest into RAG
        rag_manager = get_rag_manager()
        chunks_count = await rag_manager.ingest_file(file_path)
        
        return {
            "filename": file.filename,
            "status": "success", 
            "chunks": chunks_count,
            "message": f"Successfully ingested {file.filename} with {chunks_count} chunks."
        }
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/skills")
async def list_skills():
    """List all available skills."""
    service = DeepResearchService()
    return {"skills": service.get_skills()}

@app.post("/skills/{name}/toggle")
async def toggle_skill(name: str, enabled: bool = True):
    """Toggle a skill on/off."""
    service = DeepResearchService()
    success = service.toggle_skill(name, enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"status": "success", "enabled": enabled}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
