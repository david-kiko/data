from neo4j import GraphDatabase
import os
from typing import List, Dict, Any
import logging
import requests
import re
from dataclasses import dataclass
from typing import Optional, List, Dict
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Neo4j 连接参数
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://192.168.30.232:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j123")

# API 配置
API_URL = "http://192.168.30.231:18086/api/sql/execute"
API_HEADERS = {"Content-Type": "application/json"}

@dataclass
class TableInfo:
    name: str
    comment: str
    fields: List[Dict[str, Any]]
    references: List[Dict[str, str]]

class Neo4jImporter:
    def __init__(self):
        """初始化 Neo4j 导入器"""
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.enum_cache = {}  # 缓存枚举数据
        self.foreign_key_cache = {}  # 缓存外键数据
        
    def close(self):
        """关闭数据库连接"""
        self.driver.close()
        
    def is_database_empty(self) -> bool:
        """检查数据库是否为空，如果不为空则清空数据库"""
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()["count"]
            if count > 0:
                logger.warning(f"Neo4j数据库不为空，当前有 {count} 个节点，将清空数据库...")
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("数据库已清空")
            return True

    def fetch_enum_data(self) -> None:
        sql = "SELECT CENUM_TYPE, CNAME, CVALUE FROM KMMOM.DM_ENUM_VALUE ORDER BY CENUM_TYPE"
        response = requests.post(API_URL, json={"sql": sql}, headers=API_HEADERS)
        response.raise_for_status()
        try:
            rows = json.loads(response.text)
        except Exception as e:
            logger.error(f"无法解析API返回内容: {e}")
            return

        for row in rows:
            enum_type = row['CENUM_TYPE'].strip().lower()
            if enum_type not in self.enum_cache:
                self.enum_cache[enum_type] = []
            self.enum_cache[enum_type].append({
                'value': row['CVALUE'],
                'name': row['CNAME']
            })

    def fetch_foreign_key_data(self) -> None:
        """获取外键数据并缓存"""
        sql_basic = """
        select t1.CCOLUMN_NAME AS COLUMN_NAME, t2.CTABLE_NAME AS CTABLE, t3.CTABLE_NAME AS RTABLE 
        from KMMOM.DM_TYPE_DEFINITION_PROPERTY t1 
        JOIN KMMOM.DM_TYPE_DEFINITION t2 ON t1.CTYPE_ENTITY_TYPE = t2.CCODE 
        JOIN KMMOM.DM_TYPE_DEFINITION t3 ON t1.CREFERENCE_TYPE = t3.CCODE 
        WHERE t1.CREFERENCE_TYPE IS NOT NULL AND t2.CTABLE_NAME IS NOT NULL AND t3.CTABLE_NAME IS NOT null
        """
        sql_additional = """
        SELECT dtc.TABLE_NAME AS CTABLE, dtc.COLUMN_NAME AS COLUMN_NAME, def.CTABLE_NAME AS RTABLE 
        FROM DBA_TAB_COLUMNS dtc 
        JOIN (select t2.CCOLUMN_NAME || '_ID' AS COLUMN_NAME, t2.CREFERENCE_TYPE AS CREFERENCE_TYPE 
        FROM KMMOM.DM_TYPE_DEFINITION t1 
        join KMMOM.DM_TYPE_DEFINITION_PROPERTY t2 ON t1.CCODE = t2.CTYPE_ENTITY_TYPE 
        WHERE T1.CTABLE_NAME IS NULL AND t2.CREFERENCE_TYPE IS NOT NULL) mom_v 
        ON dtc.COLUMN_NAME = mom_v.COLUMN_NAME 
        JOIN KMMOM.DM_TYPE_DEFINITION def ON mom_v.CREFERENCE_TYPE = def.CCODE 
        WHERE dtc.OWNER = 'KMMOM' 
        ORDER BY dtc.TABLE_NAME asc
        """
        try:
            # 获取基本外键数据
            response_basic = requests.post(API_URL, json={"sql": sql_basic}, headers=API_HEADERS)
            response_basic.raise_for_status()
            rows_basic = json.loads(response_basic.text)
            logger.info(f"获取到基本外键数据: {len(rows_basic)} 条")

            # 获取额外外键数据
            response_additional = requests.post(API_URL, json={"sql": sql_additional}, headers=API_HEADERS)
            response_additional.raise_for_status()
            rows_additional = json.loads(response_additional.text)
            logger.info(f"获取到额外外键数据: {len(rows_additional)} 条")

            # 合并并处理外键数据
            self.foreign_key_cache = {}
            for row in rows_basic + rows_additional:
                from_table = row['CTABLE']
                if from_table not in self.foreign_key_cache:
                    self.foreign_key_cache[from_table] = []
                
                self.foreign_key_cache[from_table].append({
                    'from_column': row['COLUMN_NAME'],
                    'to_table': row['RTABLE'],
                    'to_column': 'CCODE'  # 默认引用CCODE字段
                })
            
            logger.info(f"处理后的外键关系总数: {sum(len(refs) for refs in self.foreign_key_cache.values())}")
            logger.info(f"涉及的表数量: {len(self.foreign_key_cache)}")
            
        except Exception as e:
            logger.error(f"获取外键数据时发生错误: {e}")
            self.foreign_key_cache = {}

    def fetch_data_from_api(self) -> List[Dict]:
        sql = """
        SELECT dtc.TABLE_NAME AS TABLE_NAME
             , mom.TABLE_COMMENT AS TABLE_COMMENT
             , dtc.COLUMN_NAME AS COLUMN_NAME
             , dtc.DATA_TYPE AS COLUMN_TYPE
             , NVL(mom.COLUMN_COMMENT, mom_v.COLUMN_COMMENT) AS COLUMN_COMMENT
             , mom.ENUM_TYPE AS ENUM_TYPE
        FROM DBA_TAB_COLUMNS dtc
        LEFT JOIN (
            select t1.CTABLE_NAME AS TABLE_NAME
                 , t1.CDISPLAY_NAME AS TABLE_COMMENT
                 , t2.CCOLUMN_NAME AS COLUMN_NAME
                 , t2.CDISPLAY_NAME AS COLUMN_COMMENT
                 , t2.CDATA_TYPE AS DATA_TYPE
                 , t2.CENUM_TYPE AS ENUM_TYPE
            from KMMOM.DM_TYPE_DEFINITION t1
            JOIN KMMOM.DM_TYPE_DEFINITION_PROPERTY t2
              ON t1.CCODE = t2.CTYPE_ENTITY_TYPE
            WHERE t1.CTABLE_NAME IS NOT NULL
              AND t2.CREFERENCE_TYPE IS NULL
            UNION
            select t1.CTABLE_NAME AS TABLE_NAME
                 , t1.CDISPLAY_NAME AS TABLE_COMMENT
                 , t2.CCOLUMN_NAME || '_ID' AS COLUMN_NAME
                 , t2.CDISPLAY_NAME || 'ID' AS COLUMN_COMMENT
                 , t2.CDATA_TYPE AS DATA_TYPE
                 , t2.CENUM_TYPE AS ENUM_TYPE
            from KMMOM.DM_TYPE_DEFINITION t1
            JOIN KMMOM.DM_TYPE_DEFINITION_PROPERTY t2
              ON t1.CCODE = t2.CTYPE_ENTITY_TYPE
            WHERE t1.CTABLE_NAME IS NOT NULL
              AND t2.CREFERENCE_TYPE IS NOT NULL
        ) mom
        ON dtc.TABLE_NAME = mom.TABLE_NAME
        AND dtc.COLUMN_NAME = mom.COLUMN_NAME
        LEFT join
        (select t2.CCOLUMN_NAME AS COLUMN_NAME
             , t2.CDISPLAY_NAME AS COLUMN_COMMENT
             , t2.CDATA_TYPE AS DATA_TYPE
             , t2.CENUM_TYPE AS ENUM_TYPE
          FROM KMMOM.DM_TYPE_DEFINITION t1
          join KMMOM.DM_TYPE_DEFINITION_PROPERTY t2
            ON t1.CCODE = t2.CTYPE_ENTITY_TYPE
         WHERE T1.CTABLE_NAME IS NULL AND t2.CREFERENCE_TYPE IS NULL
         UNION DISTINCT
         select t2.CCOLUMN_NAME || '_ID' AS COLUMN_NAME
             , t2.CDISPLAY_NAME || 'ID' AS COLUMN_COMMENT
             , t2.CDATA_TYPE AS DATA_TYPE
             , t2.CENUM_TYPE AS ENUM_TYPE
          FROM KMMOM.DM_TYPE_DEFINITION t1
          join KMMOM.DM_TYPE_DEFINITION_PROPERTY t2
            ON t1.CCODE = t2.CTYPE_ENTITY_TYPE
         WHERE T1.CTABLE_NAME IS NULL AND t2.CREFERENCE_TYPE IS NOT NULL
        ) mom_v
        ON dtc.COLUMN_NAME = mom_v.COLUMN_NAME
        WHERE dtc.OWNER = 'KMMOM'
        ORDER BY dtc.TABLE_NAME asc
        """
        logger.info("执行SQL查询...")
        response = requests.post(API_URL, json={"sql": sql}, headers=API_HEADERS)
        logger.info(f"API响应状态码: {response.status_code}")
        response.raise_for_status()
        
        try:
            rows = json.loads(response.text)
            logger.info(f"API返回数据条数: {len(rows)}")
            return rows
        except Exception as e:
            logger.error(f"无法解析API返回内容: {e}")
            return []

    def parse_table_info(self, rows: List[Dict]) -> List[TableInfo]:
        """直接解析API返回的数据"""
        tables = {}

        for row in rows:
            table_name = row['TABLE_NAME']
            table_comment = row['TABLE_COMMENT'] or ''
            if table_name not in tables:
                tables[table_name] = {
                    'name': table_name,
                    'comment': '',  # 先设为空
                    'fields': [],
                    'references': self.foreign_key_cache.get(table_name, [])
                }
            # 只要还没设置注释且当前行有注释，就赋值
            if not tables[table_name]['comment'] and table_comment:
                tables[table_name]['comment'] = table_comment

            field_info = {
                'name': row['COLUMN_NAME'],
                'type': row['COLUMN_TYPE'],
                'comment': row['COLUMN_COMMENT'] or '',
                'enums': []
            }
            if row['ENUM_TYPE']:
                enum_type = row['ENUM_TYPE'].strip().lower()
                logger.info(f"字段 {row['COLUMN_NAME']} 的枚举类型: '{enum_type}'")
                if enum_type in self.enum_cache:
                    field_info['enums'] = self.enum_cache[enum_type]
                else:
                    logger.warning(f"未找到枚举类型: '{enum_type}'，可用类型: {list(self.enum_cache.keys())}")
            tables[table_name]['fields'].append(field_info)

        # 转换为TableInfo对象列表
        return [TableInfo(**table_data) for table_data in tables.values()]

    def import_to_neo4j(self, tables: List[TableInfo]):
        """导入数据到Neo4j，并打印统计信息"""
        # 收集所有解析到的表名
        all_parsed_table_names = set(table.name for table in tables)
        logger.info(f"解析到的表总数: {len(all_parsed_table_names)}")

        written_tables = set()
        with self.driver.session() as session:
            # 使用事务批量创建表节点
            with session.begin_transaction() as tx:
                for table in tables:
                    try:
                        # 构建表的元数据字符串，包含枚举值，格式为: [值1:注释1,值2:注释2,...]
                        fields_str = ','.join(
                            "{}:{}:{}{}".format(
                                field['name'],
                                field['type'],
                                field['comment'],
                                (":[{}]".format(
                                    ",".join(
                                        "{}:{}".format(enum['value'], enum['name'])
                                        for enum in field['enums']
                                    )
                                ) if field['enums'] else "")
                            )
                            for field in table.fields
                        )
                        meta = "{}[{}]({})".format(table.name, table.comment, fields_str)
                        
                        # 创建表节点
                        tx.run(
                            """
                            CREATE (t:Table {
                                name:$name,
                                meta:$meta
                            })
                            """,
                            name=table.name,
                            meta=meta
                        )
                        written_tables.add(table.name)
                    except Exception as e:
                        logger.error(f"创建表节点失败 {table.name}: {e}")
                        continue

            # 使用事务批量创建关系
            with session.begin_transaction() as tx:
                for table in tables:
                    for ref in table.references:
                        try:
                            # 创建正向引用关系
                            tx.run(
                                """
                                MATCH (from:Table {name: $from_table})
                                MATCH (to:Table {name: $to_table})
                                CREATE (from)-[r:REFERENCES {
                                    from: $from_column,
                                    to: $to_column,
                                    created_at: datetime()
                                }]->(to)
                                """,
                                from_table=table.name,
                                to_table=ref['to_table'],
                                from_column=ref['from_column'],
                                to_column=ref['to_column']
                            )
                            
                            # 创建反向引用关系
                            tx.run(
                                """
                                MATCH (from:Table {name: $from_table})
                                MATCH (to:Table {name: $to_table})
                                CREATE (to)-[r:`REFERENCED BY` {
                                    from: $to_column,
                                    to: $from_column,
                                    created_at: datetime()
                                }]->(from)
                                """,
                                from_table=table.name,
                                to_table=ref['to_table'],
                                from_column=ref['from_column'],
                                to_column=ref['to_column']
                            )
                        except Exception as e:
                            logger.error(f"创建关系失败 {table.name} -> {ref['to_table']}: {e}")
                            continue

        # 输出导入结果统计
        logger.info(f"实际写入Neo4j的表总数: {len(written_tables)}")
        not_written = all_parsed_table_names - written_tables
        if not_written:
            logger.warning(f"未被写入的表数量: {len(not_written)}")
        else:
            logger.info("所有解析到的表都已写入Neo4j。")

def main():
    """主函数"""
    logger.info("开始导入数据...")
    importer = Neo4jImporter()
    try:
        # 检查并清空数据库
        importer.is_database_empty()
        
        # 获取枚举数据
        importer.fetch_enum_data()
        
        # 获取外键数据
        importer.fetch_foreign_key_data()
        
        # 获取数据
        rows = importer.fetch_data_from_api()
        
        # 解析数据
        tables = importer.parse_table_info(rows)
        
        # 导入数据
        importer.import_to_neo4j(tables)
        
        logger.info("数据导入完成")
        
    except Exception as e:
        logger.error(f"发生错误: {str(e)}", exc_info=True)
        raise
    finally:
        importer.close()

if __name__ == "__main__":
    main() 