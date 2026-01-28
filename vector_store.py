import os
from typing import List, Dict
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()

class VectorStoreManager:
    def __init__(self):
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        self.vector_db_path = os.getenv('VECTOR_DB_PATH', './data/vectordb')
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize vector store
        os.makedirs(self.vector_db_path, exist_ok=True)
        self.vectorstore = Chroma(
            persist_directory=self.vector_db_path,
            embedding_function=self.embeddings,
            collection_name="telegram_bot_memory"
        )
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
    
    def add_conversation(self, user_id: int, content: str, role: str, metadata: Dict = None):
        """Add conversation to vector store"""
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'user_id': user_id,
            'role': role,
            'type': 'conversation'
        })
        
        documents = [Document(page_content=content, metadata=metadata)]
        self.vectorstore.add_documents(documents)
        # self.vectorstore.persist()
    
    def add_image_analysis(self, user_id: int, analysis: str, caption: str = "", image_id: int = None):
        """Add image analysis to vector store"""
        content = f"Image: {caption}\nAnalysis: {analysis}"
        metadata = {
            'user_id': user_id,
            'type': 'image',
            'image_id': image_id
        }
        
        documents = [Document(page_content=content, metadata=metadata)]
        self.vectorstore.add_documents(documents)
        # self.vectorstore.persist()
    
    def add_voice_transcription(self, user_id: int, transcription: str, voice_id: int = None):
        """Add voice transcription to vector store"""
        metadata = {
            'user_id': user_id,
            'type': 'voice',
            'voice_id': voice_id
        }
        
        documents = [Document(page_content=transcription, metadata=metadata)]
        self.vectorstore.add_documents(documents)
        # self.vectorstore.persist()
    
    def add_list(self, user_id: int, list_name: str, items: List[str]):
        """Add list to vector store"""
        content = f"List: {list_name}\nItems: {', '.join(items)}"
        metadata = {
            'user_id': user_id,
            'type': 'list',
            'list_name': list_name
        }
        
        documents = [Document(page_content=content, metadata=metadata)]
        self.vectorstore.add_documents(documents)
        # self.vectorstore.persist()
    
    def add_reminder(self, user_id: int, reminder_content: str, reminder_time: str):
        """Add reminder to vector store"""
        content = f"Reminder: {reminder_content}\nTime: {reminder_time}"
        metadata = {
            'user_id': user_id,
            'type': 'reminder'
        }
        
        documents = [Document(page_content=content, metadata=metadata)]
        self.vectorstore.add_documents(documents)
        # self.vectorstore.persist()
    
    def search_memory(self, user_id: int, query: str, k: int = 5) -> List[Document]:
        """Search user's memory"""
        results = self.vectorstore.similarity_search(
            query,
            k=k,
            filter={'user_id': user_id}
        )
        return results
    
    def search_images(self, user_id: int, query: str, k: int = 3) -> List[Document]:
        """Search for images based on query"""
        results = self.vectorstore.similarity_search(
            query,
            k=k,
            filter={'user_id': user_id, 'type': 'image'}
        )
        return results
    
    def get_recent_context(self, user_id: int, k: int = 5) -> List[Document]:
        """Get recent conversation context"""
        # This is a simplified version - in production, you'd want to sort by timestamp
        results = self.vectorstore.similarity_search(
            "",
            k=k,
            filter={'user_id': user_id, 'type': 'conversation'}
        )
        return results