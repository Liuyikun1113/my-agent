"""
向量嵌入存储
提供向量嵌入的生成、存储和检索功能
"""
import logging
from typing import Optional, List, Dict, Any, Tuple, Union
import json
from datetime import datetime
import uuid

from .milvus_client import milvus_client, MilvusClient
from backend.src.memory.interfaces.memory_item import MemoryItem
from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """
    向量嵌入存储
    管理向量嵌入的生成和存储
    """

    def __init__(self, client: Optional[MilvusClient] = None):
        """
        初始化嵌入存储

        Args:
            client: Milvus客户端实例，如果为None则使用全局实例
        """
        self.client = client or milvus_client
        self._embedding_model = None
        self._initialized = False

    async def initialize(self):
        """
        初始化嵌入存储
        """
        if self._initialized:
            return

        try:
            # 初始化Milvus客户端
            await self.client.initialize()

            # 尝试加载嵌入模型
            await self._load_embedding_model()

            self._initialized = True
            logger.info("向量嵌入存储初始化完成")

        except Exception as e:
            logger.error(f"向量嵌入存储初始化失败: {e}", exc_info=True)
            raise

    async def _load_embedding_model(self):
        """
        加载嵌入模型
        支持多种模型：BERT, Sentence Transformers, OpenAI embeddings等
        """
        try:
            # 尝试加载Sentence Transformers
            try:
                from sentence_transformers import SentenceTransformer
                model_name = getattr(settings, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
                self._embedding_model = SentenceTransformer(model_name)
                logger.info(f"加载Sentence Transformer模型: {model_name}")
                return
            except ImportError:
                logger.warning("sentence_transformers未安装，尝试其他模型")

            # 尝试加载BERT
            try:
                from transformers import AutoTokenizer, AutoModel
                import torch
                model_name = getattr(settings, "EMBEDDING_MODEL", "bert-base-uncased")
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._model = AutoModel.from_pretrained(model_name)
                logger.info(f"加载BERT模型: {model_name}")
                return
            except ImportError:
                logger.warning("transformers未安装，无法使用本地嵌入模型")

            # 如果没有本地模型，记录警告
            logger.warning("未找到本地嵌入模型，将使用占位嵌入或外部API")

        except Exception as e:
            logger.error(f"加载嵌入模型失败: {e}")
            # 模型加载失败不影响基本功能，继续

    async def generate_embedding(
        self,
        text: str,
        model_type: Optional[str] = None,
    ) -> List[float]:
        """
        生成文本嵌入向量

        Args:
            text: 输入文本
            model_type: 模型类型（可选）

        Returns:
            List[float]: 嵌入向量
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 如果使用本地模型
            if self._embedding_model:
                # Sentence Transformer
                if hasattr(self._embedding_model, 'encode'):
                    embedding = self._embedding_model.encode(text, normalize_embeddings=True)
                    return embedding.tolist()
                # BERT
                elif hasattr(self, '_tokenizer') and hasattr(self, '_model'):
                    import torch
                    inputs = self._tokenizer(text, return_tensors="pt", padding=True, truncation=True)
                    with torch.no_grad():
                        outputs = self._model(**inputs)
                    # 使用CLS token的嵌入
                    embedding = outputs.last_hidden_state[:, 0, :].squeeze().tolist()
                    return embedding

            # 如果没有本地模型，使用占位嵌入
            logger.warning("使用占位嵌入，实际应用中应配置嵌入模型")
            return self._generate_placeholder_embedding(text)

        except Exception as e:
            logger.error(f"生成嵌入向量失败: text={text[:50]}..., error={e}", exc_info=True)
            # 返回占位嵌入
            return self._generate_placeholder_embedding(text)

    def _generate_placeholder_embedding(self, text: str) -> List[float]:
        """
        生成占位嵌入向量（用于测试和开发）

        Args:
            text: 输入文本

        Returns:
            List[float]: 占位嵌入向量
        """
        import hashlib
        import numpy as np

        # 使用文本哈希生成伪随机向量
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()

        # 将哈希转换为固定长度的向量
        vector_dim = self.client.vector_dim if hasattr(self.client, 'vector_dim') else 768
        np.random.seed(int(hash_hex[:8], 16))
        embedding = np.random.randn(vector_dim).tolist()

        # 归一化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()

        return embedding

    async def store_memory_item(
        self,
        memory_item: MemoryItem,
        generate_embedding: bool = True,
    ) -> bool:
        """
        存储记忆项到向量数据库

        Args:
            memory_item: 记忆项
            generate_embedding: 是否生成嵌入向量

        Returns:
            bool: 是否存储成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 准备向量数据
            vector_data = {
                "id": memory_item.id,
                "type": memory_item.type,
                "text": self._extract_text_for_embedding(memory_item),
                "data": memory_item.data,
                "metadata": memory_item.metadata,
                "created_at": int(memory_item.created_at.timestamp()),
                "updated_at": int(memory_item.updated_at.timestamp()),
            }

            # 生成或使用现有嵌入
            if generate_embedding and not memory_item.embedding:
                # 从数据中提取文本用于生成嵌入
                text_for_embedding = self._extract_text_for_embedding(memory_item)
                embedding = await self.generate_embedding(text_for_embedding)
                vector_data["embedding"] = embedding
                memory_item.embedding = embedding
            elif memory_item.embedding:
                vector_data["embedding"] = memory_item.embedding
            else:
                # 如果没有嵌入，生成一个
                text_for_embedding = self._extract_text_for_embedding(memory_item)
                embedding = await self.generate_embedding(text_for_embedding)
                vector_data["embedding"] = embedding
                memory_item.embedding = embedding

            # 存储到Milvus
            await self.client.insert([vector_data])

            logger.debug(f"存储记忆项到向量数据库: id={memory_item.id}, type={memory_item.type}")

            return True

        except Exception as e:
            logger.error(f"存储记忆项到向量数据库失败: id={memory_item.id}, error={e}", exc_info=True)
            return False

    def _extract_text_for_embedding(self, memory_item: MemoryItem) -> str:
        """
        从记忆项中提取文本用于生成嵌入

        Args:
            memory_item: 记忆项

        Returns:
            str: 提取的文本
        """
        # 根据类型提取文本
        if memory_item.type == "message":
            content = memory_item.data.get("content", "")
            if content:
                return content

        elif memory_item.type == "document":
            text = memory_item.data.get("text", "")
            if text:
                return text

        elif memory_item.type == "summary":
            summary = memory_item.data.get("summary", "")
            if summary:
                return summary

        # 默认：使用数据中的文本字段或转换为字符串
        for field in ["text", "content", "title", "description", "name"]:
            if field in memory_item.data:
                value = memory_item.data[field]
                if isinstance(value, str) and value.strip():
                    return value.strip()

        # 如果没有找到文本，使用数据本身的字符串表示
        return str(memory_item.data)[:1000]

    async def search_similar(
        self,
        query: Union[str, List[float], MemoryItem],
        filter_type: Optional[str] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        搜索相似的记忆项

        Args:
            query: 查询内容（文本、向量或记忆项）
            filter_type: 过滤类型
            limit: 返回数量
            min_score: 最小相似度分数

        Returns:
            List[Dict[str, Any]]: 相似记忆项列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 获取查询向量
            if isinstance(query, str):
                query_vector = await self.generate_embedding(query)
            elif isinstance(query, list):
                query_vector = query
            elif isinstance(query, MemoryItem):
                if query.embedding:
                    query_vector = query.embedding
                else:
                    text_for_embedding = self._extract_text_for_embedding(query)
                    query_vector = await self.generate_embedding(text_for_embedding)
            else:
                raise ValueError(f"不支持的查询类型: {type(query)}")

            # 构建过滤表达式
            filter_expr = None
            if filter_type:
                filter_expr = f"type == '{filter_type}'"

            # 执行搜索
            search_results = await self.client.search(
                query_vector=query_vector,
                filter_expr=filter_expr,
                limit=limit * 2,  # 多取一些，用于过滤
            )

            # 过滤和转换结果
            similar_items = []
            for result in search_results:
                score = result.get("score", 0.0)

                if score < min_score:
                    continue

                # 转换为MemoryItem
                try:
                    memory_item = MemoryItem.from_dict({
                        "id": result["id"],
                        "type": result["type"],
                        "data": result["data"],
                        "metadata": result["metadata"],
                        "created_at": datetime.fromtimestamp(result["created_at"]),
                        "updated_at": datetime.fromtimestamp(result["updated_at"]),
                        "embedding": result.get("embedding"),
                    })

                    similar_items.append({
                        "item": memory_item,
                        "score": score,
                        "distance": result.get("distance", 0.0),
                        "metadata": result.get("metadata", {}),
                    })

                except Exception as e:
                    logger.error(f"转换搜索结果失败: result={result}, error={e}")
                    continue

                # 达到限制数量
                if len(similar_items) >= limit:
                    break

            # 按分数排序
            similar_items.sort(key=lambda x: x["score"], reverse=True)

            logger.debug(f"相似性搜索完成: 查询类型={type(query).__name__}, 结果数量={len(similar_items)}")

            return similar_items

        except Exception as e:
            logger.error(f"相似性搜索失败: query={query}, error={e}", exc_info=True)
            return []

    async def search_hybrid(
        self,
        query_text: str,
        filter_type: Optional[str] = None,
        limit: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量语义 + BM25 关键词，RRF 融合排序

        Args:
            query_text: 查询文本
            filter_type: 过滤类型
            limit: 返回数量
            vector_weight: 向量检索权重（0-1）
            text_weight: BM25 权重（0-1）
            min_score: 最小分数阈值

        Returns:
            List[Dict[str, Any]]: 混合检索结果
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 生成查询向量
            query_vector = await self.generate_embedding(query_text)

            # 构建过滤表达式
            filter_expr = f"type == '{filter_type}'" if filter_type else None

            # 调用 Milvus 混合检索
            raw_results = await self.client.search_hybrid(
                query_text=query_text,
                query_vector=query_vector,
                filter_expr=filter_expr,
                vector_limit=limit * 2,
                text_limit=limit * 2,
                fusion_limit=limit,
                vector_weight=vector_weight,
                text_weight=text_weight,
            )

            # 转换为 MemoryItem 格式
            results = []
            for r in raw_results:
                score = r.get("score", 0.0)
                if score < min_score:
                    continue

                try:
                    memory_item = MemoryItem.from_dict({
                        "id": r["id"],
                        "type": r["type"],
                        "data": r.get("data", {}),
                        "metadata": r.get("metadata", {}),
                        "created_at": datetime.fromtimestamp(r["created_at"]),
                        "updated_at": datetime.fromtimestamp(r["updated_at"]),
                        "embedding": r.get("embedding"),
                    })
                    results.append({
                        "item": memory_item,
                        "score": score,
                        "text": r.get("text", ""),
                        "metadata": r.get("metadata", {}),
                    })
                except Exception as e:
                    logger.error(f"转换混合检索结果失败: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"混合检索失败: query={query_text}, error={e}", exc_info=True)
            return []

    async def batch_store(
        self,
        memory_items: List[MemoryItem],
        batch_size: int = 50,
        generate_embeddings: bool = True,
    ) -> Tuple[int, int]:
        """
        批量存储记忆项

        Args:
            memory_items: 记忆项列表
            batch_size: 批量大小
            generate_embeddings: 是否生成嵌入向量

        Returns:
            Tuple[int, int]: (成功数量, 失败数量)
        """
        if not self._initialized:
            await self.initialize()

        success_count = 0
        fail_count = 0

        try:
            total_items = len(memory_items)
            logger.info(f"开始批量存储 {total_items} 个记忆项")

            for i in range(0, total_items, batch_size):
                batch = memory_items[i:i + batch_size]
                batch_vectors = []

                # 准备批次数据
                for item in batch:
                    try:
                        vector_data = {
                            "id": item.id,
                            "type": item.type,
                            "text": self._extract_text_for_embedding(item),
                            "data": item.data,
                            "metadata": item.metadata,
                            "created_at": int(item.created_at.timestamp()),
                            "updated_at": int(item.updated_at.timestamp()),
                        }

                        if generate_embeddings and not item.embedding:
                            text_for_embedding = self._extract_text_for_embedding(item)
                            embedding = await self.generate_embedding(text_for_embedding)
                            vector_data["embedding"] = embedding
                            item.embedding = embedding
                        elif item.embedding:
                            vector_data["embedding"] = item.embedding
                        else:
                            text_for_embedding = self._extract_text_for_embedding(item)
                            embedding = await self.generate_embedding(text_for_embedding)
                            vector_data["embedding"] = embedding
                            item.embedding = embedding

                        batch_vectors.append(vector_data)

                    except Exception as e:
                        logger.error(f"准备记忆项向量数据失败: id={item.id}, error={e}")
                        fail_count += 1
                        continue

                # 存储批次
                if batch_vectors:
                    try:
                        await self.client.insert(batch_vectors)
                        success_count += len(batch_vectors)
                        logger.debug(f"批次存储成功: {len(batch_vectors)} 项，累计 {success_count}/{total_items}")
                    except Exception as e:
                        logger.error(f"批次存储失败: error={e}")
                        fail_count += len(batch_vectors)

            logger.info(f"批量存储完成: 成功 {success_count}, 失败 {fail_count}, 总计 {total_items}")

            return success_count, fail_count

        except Exception as e:
            logger.error(f"批量存储失败: error={e}", exc_info=True)
            return success_count, total_items - success_count

    async def delete_memory_item(
        self,
        memory_item_id: str,
    ) -> bool:
        """
        从向量数据库中删除记忆项

        Args:
            memory_item_id: 记忆项ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            deleted_count = await self.client.delete(ids=[memory_item_id])
            success = deleted_count > 0

            if success:
                logger.debug(f"从向量数据库删除记忆项: id={memory_item_id}")
            else:
                logger.warning(f"未找到要删除的记忆项: id={memory_item_id}")

            return success

        except Exception as e:
            logger.error(f"从向量数据库删除记忆项失败: id={memory_item_id}, error={e}", exc_info=True)
            return False

    async def get_memory_item(
        self,
        memory_item_id: str,
        include_embedding: bool = False,
    ) -> Optional[MemoryItem]:
        """
        从向量数据库获取记忆项

        Args:
            memory_item_id: 记忆项ID
            include_embedding: 是否包含嵌入向量

        Returns:
            Optional[MemoryItem]: 记忆项，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 设置输出字段
            output_fields = ["id", "type", "data", "metadata", "created_at", "updated_at"]
            if include_embedding:
                output_fields.append("embedding")

            # 查询
            result = await self.client.get_by_id(
                item_id=memory_item_id,
                output_fields=output_fields,
            )

            if not result:
                return None

            # 转换为MemoryItem
            memory_item = MemoryItem.from_dict({
                "id": result["id"],
                "type": result["type"],
                "data": result["data"],
                "metadata": result["metadata"],
                "created_at": datetime.fromtimestamp(result["created_at"]),
                "updated_at": datetime.fromtimestamp(result["updated_at"]),
                "embedding": result.get("embedding") if include_embedding else None,
            })

            return memory_item

        except Exception as e:
            logger.error(f"从向量数据库获取记忆项失败: id={memory_item_id}, error={e}", exc_info=True)
            return None

    async def count_items(
        self,
        filter_type: Optional[str] = None,
    ) -> int:
        """
        统计向量数据库中的记忆项数量

        Args:
            filter_type: 过滤类型

        Returns:
            int: 记忆项数量
        """
        if not self._initialized:
            await self.initialize()

        try:
            filter_expr = None
            if filter_type:
                filter_expr = f"type == '{filter_type}'"

            return await self.client.count(filter_expr)

        except Exception as e:
            logger.error(f"统计向量数据库记忆项数量失败: error={e}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            await self.initialize()

            # 检查Milvus客户端
            client_health = await self.client.health_check()

            # 检查嵌入模型
            model_status = "loaded" if self._embedding_model else "not_loaded"

            # 统计信息
            total_items = await self.count_items()

            return {
                "status": client_health.get("status", "unknown"),
                "message": client_health.get("message", ""),
                "collection_name": client_health.get("collection_name", ""),
                "entity_count": total_items,
                "embedding_model": model_status,
                "initialized": self._initialized,
                "client_health": client_health,
            }

        except Exception as e:
            logger.error(f"向量嵌入存储健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"向量嵌入存储检查失败: {str(e)}",
                "collection_name": self.client.collection_name if hasattr(self.client, 'collection_name') else "",
                "entity_count": 0,
                "embedding_model": "unknown",
                "initialized": self._initialized,
            }

    async def close(self):
        """
        关闭嵌入存储
        """
        try:
            await self.client.close()
            self._initialized = False
            logger.info("向量嵌入存储已关闭")

        except Exception as e:
            logger.error(f"关闭向量嵌入存储失败: {e}")


# 全局嵌入存储实例
embedding_store = EmbeddingStore()