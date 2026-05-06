"""
Milvus向量数据库客户端
提供Milvus连接管理和集合操作
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union, Tuple
import json
from datetime import datetime
import uuid

# 尝试导入pymilvus
try:
    from pymilvus import (
        connections,
        Collection,
        CollectionSchema,
        FieldSchema,
        DataType,
        utility,
        db,
    )
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    # 创建占位类以便类型提示
    class Collection:
        pass
    class CollectionSchema:
        pass
    class FieldSchema:
        pass

from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class MilvusClient:
    """
    Milvus客户端
    管理Milvus连接和集合操作
    """

    # 默认集合名称
    DEFAULT_COLLECTION_NAME = "memory_items"

    # 默认向量维度（根据使用的嵌入模型）
    DEFAULT_VECTOR_DIM = 768  # BERT base的维度

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        vector_dim: int = DEFAULT_VECTOR_DIM,
    ):
        """
        初始化Milvus客户端

        Args:
            collection_name: 集合名称
            vector_dim: 向量维度
        """
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self.collection: Optional[Collection] = None
        self._initialized = False
        self._connection_alias = f"default_{uuid.uuid4().hex[:8]}"

        # 检查Milvus是否可用
        if not MILVUS_AVAILABLE:
            logger.warning("pymilvus未安装，Milvus功能将不可用")

    async def initialize(self):
        """
        初始化Milvus连接
        """
        if self._initialized:
            return

        if not MILVUS_AVAILABLE:
            logger.error("pymilvus未安装，无法初始化Milvus客户端")
            raise ImportError("pymilvus未安装，请运行: pip install pymilvus")

        try:
            # 读取Milvus配置
            milvus_host = getattr(settings, "MILVUS_HOST", "localhost")
            milvus_port = getattr(settings, "MILVUS_PORT", 19530)
            milvus_user = getattr(settings, "MILVUS_USER", "")
            milvus_password = getattr(settings, "MILVUS_PASSWORD", "")

            # 连接Milvus
            connection_params = {
                "host": milvus_host,
                "port": str(milvus_port),
                "alias": self._connection_alias,
            }

            # 如果有认证信息，添加认证
            if milvus_user and milvus_password:
                connection_params.update({
                    "user": milvus_user,
                    "password": milvus_password,
                })

            connections.connect(**connection_params)

            logger.info(f"Milvus连接成功: {milvus_host}:{milvus_port}")

            # 检查集合是否存在，不存在则创建
            await self._ensure_collection()

            self._initialized = True
            logger.info(f"Milvus客户端初始化完成 (collection: {self.collection_name})")

        except Exception as e:
            logger.error(f"Milvus客户端初始化失败: {e}", exc_info=True)
            # 断开连接
            try:
                connections.disconnect(self._connection_alias)
            except:
                pass
            raise

    async def _ensure_collection(self):
        """
        确保集合存在
        """
        try:
            # 检查集合是否存在
            if utility.has_collection(self.collection_name, using=self._connection_alias):
                logger.info(f"集合已存在: {self.collection_name}")
                self.collection = Collection(
                    self.collection_name,
                    using=self._connection_alias
                )
                # 加载集合到内存
                self.collection.load()
            else:
                logger.info(f"创建新集合: {self.collection_name}")
                await self._create_collection()

        except Exception as e:
            logger.error(f"确保集合存在失败: {e}", exc_info=True)
            raise

    async def _create_collection(self):
        """
        创建Milvus集合
        """
        try:
            # 定义字段
            fields = [
                # 主键字段
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    max_length=36,
                    is_primary=True,
                ),
                # 向量字段
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.vector_dim,
                ),
                # 记忆项类型
                FieldSchema(
                    name="type",
                    dtype=DataType.VARCHAR,
                    max_length=50,
                ),
                # 纯文本字段（用于BM25关键词检索，启用分词器）
                FieldSchema(
                    name="text",
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                    enable_analyzer=True,
                ),
                # 原始数据（JSON格式，保存完整结构化信息）
                FieldSchema(
                    name="data",
                    dtype=DataType.JSON,
                ),
                # 元数据（JSON格式）
                FieldSchema(
                    name="metadata",
                    dtype=DataType.JSON,
                ),
                # 创建时间
                FieldSchema(
                    name="created_at",
                    dtype=DataType.INT64,
                ),
                # 更新时间
                FieldSchema(
                    name="updated_at",
                    dtype=DataType.INT64,
                ),
            ]

            # 创建集合模式
            schema = CollectionSchema(
                fields=fields,
                description="记忆项向量存储",
                enable_dynamic_field=False,
            )

            # 创建集合
            self.collection = Collection(
                name=self.collection_name,
                schema=schema,
                using=self._connection_alias,
            )

            logger.info(f"集合创建成功: {self.collection_name}")

            # 创建索引
            await self._create_index()

            # 加载集合到内存
            self.collection.load()

        except Exception as e:
            logger.error(f"创建集合失败: {e}", exc_info=True)
            raise

    async def _create_index(self):
        """
        创建向量索引和全文索引
        """
        try:
            # 向量字段索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }

            self.collection.create_index(
                field_name="embedding",
                index_params=index_params,
                index_name="embedding_index",
            )

            # type 字段索引
            self.collection.create_index(
                field_name="type",
                index_params={"index_type": "Trie"},
                index_name="type_index",
            )

            # created_at 排序索引
            self.collection.create_index(
                field_name="created_at",
                index_params={"index_type": "STL_SORT"},
                index_name="created_at_index",
            )

            logger.info(f"集合索引创建成功: {self.collection_name}")

        except Exception as e:
            logger.error(f"创建索引失败: {e}", exc_info=True)
            logger.warning("索引创建失败，向量搜索性能可能受影响")

    async def insert(
        self,
        items: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> List[str]:
        """
        插入向量数据

        Args:
            items: 数据项列表，每个项必须包含:
                   - id: 唯一标识符
                   - embedding: 向量嵌入
                   - type: 类型
                   - data: 原始数据
                   - metadata: 元数据
                   - created_at: 创建时间戳（秒）
                   - updated_at: 更新时间戳（秒）
            batch_size: 批量大小

        Returns:
            List[str]: 成功插入的ID列表
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            # 准备数据
            ids = []
            embeddings = []
            types = []
            texts = []
            data_list = []
            metadata_list = []
            created_at_list = []
            updated_at_list = []

            for item in items:
                # 验证必要字段
                required_fields = ["id", "embedding", "type"]
                for field in required_fields:
                    if field not in item:
                        raise ValueError(f"缺少必要字段: {field}")

                ids.append(str(item["id"]))
                embeddings.append(item["embedding"])
                types.append(str(item["type"]))
                texts.append(str(item.get("text", "")))
                data_list.append(json.dumps(item.get("data", {})))
                metadata_list.append(json.dumps(item.get("metadata", {})))
                created_at_list.append(item.get("created_at", int(datetime.now().timestamp())))
                updated_at_list.append(item.get("updated_at", int(datetime.now().timestamp())))

            # 分批插入
            inserted_ids = []
            total_items = len(ids)

            for i in range(0, total_items, batch_size):
                end_idx = min(i + batch_size, total_items)

                batch_data = [
                    ids[i:end_idx],
                    embeddings[i:end_idx],
                    types[i:end_idx],
                    texts[i:end_idx],
                    data_list[i:end_idx],
                    metadata_list[i:end_idx],
                    created_at_list[i:end_idx],
                    updated_at_list[i:end_idx],
                ]

                # 插入数据
                insert_result = self.collection.insert(batch_data)
                inserted_ids.extend(ids[i:end_idx])

                logger.debug(f"插入 {len(batch_data[0])} 个向量项，累计 {len(inserted_ids)}/{total_items}")

            # 刷新数据
            self.collection.flush()

            logger.info(f"向量数据插入完成: 共 {len(inserted_ids)} 项")

            return inserted_ids

        except Exception as e:
            logger.error(f"插入向量数据失败: {e}", exc_info=True)
            raise

    async def search(
        self,
        query_vector: List[float],
        filter_expr: Optional[str] = None,
        limit: int = 10,
        output_fields: Optional[List[str]] = None,
        search_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量相似性搜索

        Args:
            query_vector: 查询向量
            filter_expr: 过滤表达式（Milvus表达式语法）
            limit: 返回结果数量
            output_fields: 输出字段列表
            search_params: 搜索参数

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            # 设置默认输出字段
            if output_fields is None:
                output_fields = ["id", "type", "data", "metadata", "created_at", "updated_at", "distance"]

            # 设置默认搜索参数
            if search_params is None:
                search_params = {
                    "metric_type": "COSINE",
                    "params": {"nprobe": 10},  # 搜索的聚类中心数量
                }

            # 执行搜索
            search_result = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=output_fields,
            )

            # 处理结果
            results = []
            for hits in search_result:
                for hit in hits:
                    # 解析JSON字段
                    data = {}
                    metadata = {}

                    try:
                        data = json.loads(hit.entity.get("data", "{}"))
                    except:
                        data = {}

                    try:
                        metadata = json.loads(hit.entity.get("metadata", "{}"))
                    except:
                        metadata = {}

                    result = {
                        "id": hit.entity.get("id"),
                        "type": hit.entity.get("type"),
                        "data": data,
                        "metadata": metadata,
                        "created_at": hit.entity.get("created_at"),
                        "updated_at": hit.entity.get("updated_at"),
                        "score": 1 - hit.distance,  # 余弦相似度转换为相似度分数
                        "distance": hit.distance,
                    }

                    results.append(result)

            logger.debug(f"向量搜索完成: 查询维度={len(query_vector)}, 结果数量={len(results)}")

            return results

        except Exception as e:
            logger.error(f"向量搜索失败: {e}", exc_info=True)
            return []

    async def search_text(
        self,
        query_text: str,
        filter_expr: Optional[str] = None,
        limit: int = 10,
        output_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        BM25 关键词全文检索

        Args:
            query_text: 查询关键词
            filter_expr: 过滤表达式
            limit: 返回数量
            output_fields: 输出字段

        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            if output_fields is None:
                output_fields = ["id", "type", "text", "data", "metadata", "created_at", "updated_at"]

            # 使用 BM25 Function 的输��字段进行关键词检索
            search_params = {
                "metric_type": "BM25",
            }

            # BM25 直接在 text 分词字段上检索
            search_result = self.collection.search(
                data=[query_text],
                anns_field="text",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=output_fields,
            )

            results = []
            for hits in search_result:
                for hit in hits:
                    data = {}
                    metadata = {}
                    try:
                        data = json.loads(hit.entity.get("data", "{}"))
                    except Exception:
                        data = {}
                    try:
                        metadata = json.loads(hit.entity.get("metadata", "{}"))
                    except Exception:
                        metadata = {}

                    results.append({
                        "id": hit.entity.get("id"),
                        "type": hit.entity.get("type"),
                        "text": hit.entity.get("text", ""),
                        "data": data,
                        "metadata": metadata,
                        "created_at": hit.entity.get("created_at"),
                        "updated_at": hit.entity.get("updated_at"),
                        "score": float(hit.score),
                    })

            logger.debug(f"BM25搜索完成: query='{query_text[:50]}...', 结果={len(results)}")
            return results

        except Exception as e:
            logger.error(f"BM25搜索失败: {e}", exc_info=True)
            return []

    async def search_hybrid(
        self,
        query_text: str,
        query_vector: List[float],
        filter_expr: Optional[str] = None,
        vector_limit: int = 20,
        text_limit: int = 20,
        fusion_limit: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        output_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        混合检索：向量语义搜索 + BM25 关键词搜索，RRF 融合排序

        Args:
            query_text: 查询文本（用于 BM25）
            query_vector: 查询向量（用于向量检索）
            filter_expr: 过滤表达式
            vector_limit: 向量检索候选数
            text_limit: BM25 检索候选数
            fusion_limit: 融合后返回数
            vector_weight: 向量检索权重
            text_weight: BM25 权重

        Returns:
            List[Dict[str, Any]]: 混合排序后的结果
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 并行执行向量检索和 BM25 检索
            vector_results, text_results = await asyncio.gather(
                self.search(query_vector, filter_expr, vector_limit, output_fields),
                self.search_text(query_text, filter_expr, text_limit, output_fields),
            )

            # RRF (Reciprocal Rank Fusion) 融合
            fused: Dict[str, Dict[str, Any]] = {}

            # 向量结果排名分
            for rank, item in enumerate(vector_results, start=1):
                item_id = item["id"]
                fused[item_id] = {
                    **item,
                    "_rrf_score": (vector_weight / (60 + rank)),
                }

            # BM25 结果排名分
            for rank, item in enumerate(text_results, start=1):
                item_id = item["id"]
                rrf_bonus = text_weight / (60 + rank)
                if item_id in fused:
                    fused[item_id]["_rrf_score"] += rrf_bonus
                else:
                    fused[item_id] = {**item, "_rrf_score": rrf_bonus}

            # 按融合分数降序排列
            sorted_results = sorted(
                fused.values(),
                key=lambda x: x["_rrf_score"],
                reverse=True,
            )[:fusion_limit]

            # 清理内部评分字段
            for r in sorted_results:
                r.pop("_rrf_score", None)

            logger.debug(
                f"混合检索完成: query='{query_text[:30]}...', "
                f"向量候选={len(vector_results)}, BM25候选={len(text_results)}, "
                f"融合结果={len(sorted_results)}"
            )

            return sorted_results

        except Exception as e:
            logger.error(f"混合检索失败: {e}", exc_info=True)
            return []

    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
    ) -> int:
        """
        删除向量数据

        Args:
            ids: 要删除的ID列表
            filter_expr: 过滤表达式

        Returns:
            int: 删除的数量
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            # 构建删除表达式
            if ids and filter_expr:
                expr = f"id in {ids} and ({filter_expr})"
            elif ids:
                id_list = [f"'{id}'" for id in ids]
                expr = f"id in [{','.join(id_list)}]"
            elif filter_expr:
                expr = filter_expr
            else:
                raise ValueError("必须提供ids或filter_expr参数")

            # 执行删除
            delete_result = self.collection.delete(expr)

            # 刷新数据
            self.collection.flush()

            deleted_count = delete_result.delete_count
            logger.info(f"删除向量数据: {deleted_count} 项")

            return deleted_count

        except Exception as e:
            logger.error(f"删除向量数据失败: {e}", exc_info=True)
            raise

    async def get_by_id(
        self,
        item_id: str,
        output_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        根据ID获取向量数据

        Args:
            item_id: 项目ID
            output_fields: 输出字段列表

        Returns:
            Optional[Dict[str, Any]]: 数据项，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            # 设置默认输出字段
            if output_fields is None:
                output_fields = ["id", "embedding", "type", "data", "metadata", "created_at", "updated_at"]

            # 查询表达式
            expr = f"id == '{item_id}'"

            # 执行查询
            query_result = self.collection.query(
                expr=expr,
                output_fields=output_fields,
                limit=1,
            )

            if not query_result:
                return None

            item = query_result[0]

            # 解析JSON字段
            data = {}
            metadata = {}

            try:
                data = json.loads(item.get("data", "{}"))
            except:
                data = {}

            try:
                metadata = json.loads(item.get("metadata", "{}"))
            except:
                metadata = {}

            result = {
                "id": item.get("id"),
                "embedding": item.get("embedding"),
                "type": item.get("type"),
                "data": data,
                "metadata": metadata,
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }

            return result

        except Exception as e:
            logger.error(f"根据ID获取向量数据失败: item_id={item_id}, error={e}", exc_info=True)
            return None

    async def count(
        self,
        filter_expr: Optional[str] = None,
    ) -> int:
        """
        统计向量数据数量

        Args:
            filter_expr: 过滤表达式

        Returns:
            int: 数量
        """
        if not self._initialized:
            await self.initialize()

        if not self.collection:
            raise ValueError("集合未初始化")

        try:
            count_result = self.collection.query(
                expr=filter_expr or "",
                output_fields=["count(*)"],
                limit=1,
            )

            if count_result and "count(*)" in count_result[0]:
                return count_result[0]["count(*)"]
            else:
                # 备用方法：使用Milvus的count_entities
                return self.collection.num_entities

        except Exception as e:
            logger.error(f"统计向量数据数量失败: {e}", exc_info=True)
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            if not MILVUS_AVAILABLE:
                return {
                    "status": "unhealthy",
                    "message": "pymilvus未安装",
                    "collection_name": self.collection_name,
                    "initialized": self._initialized,
                }

            await self.initialize()

            # 检查连接状态
            conn_status = connections.get_connection_addr(self._connection_alias)
            if not conn_status:
                return {
                    "status": "unhealthy",
                    "message": "Milvus连接失败",
                    "collection_name": self.collection_name,
                    "initialized": self._initialized,
                }

            # 检查集合状态
            if not self.collection:
                return {
                    "status": "unhealthy",
                    "message": "集合未初始化",
                    "collection_name": self.collection_name,
                    "initialized": self._initialized,
                }

            # 获取集合统计信息
            try:
                entity_count = self.collection.num_entities
                collection_info = {
                    "entity_count": entity_count,
                    "collection_name": self.collection.name,
                    "schema": str(self.collection.schema),
                }

                return {
                    "status": "healthy",
                    "message": "Milvus连接正常",
                    "collection_name": self.collection_name,
                    "entity_count": entity_count,
                    "initialized": self._initialized,
                    "collection_info": collection_info,
                }

            except Exception as e:
                logger.error(f"获取集合信息失败: {e}")
                return {
                    "status": "unhealthy",
                    "message": f"集合状态检查失败: {str(e)}",
                    "collection_name": self.collection_name,
                    "initialized": self._initialized,
                }

        except Exception as e:
            logger.error(f"Milvus健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"Milvus健康检查失败: {str(e)}",
                "collection_name": self.collection_name,
                "initialized": self._initialized,
            }

    async def close(self):
        """
        关闭Milvus连接
        """
        try:
            if self.collection:
                # 释放集合
                self.collection.release()

            # 断开连接
            connections.disconnect(self._connection_alias)

            self._initialized = False
            self.collection = None

            logger.info("Milvus连接已关闭")

        except Exception as e:
            logger.error(f"关闭Milvus连接失败: {e}")

    async def drop_collection(self):
        """
        删除集合
        警告：此操作会删除所有数据！
        """
        if not self._initialized:
            await self.initialize()

        try:
            utility.drop_collection(self.collection_name, using=self._connection_alias)
            self.collection = None

            logger.warning(f"删除集合: {self.collection_name}")

        except Exception as e:
            logger.error(f"删除集合失败: {e}", exc_info=True)
            raise


# 全局Milvus客户端实例（默认）
milvus_client = MilvusClient()