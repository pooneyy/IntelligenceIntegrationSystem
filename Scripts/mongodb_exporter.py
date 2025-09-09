import json
import argparse
import subprocess
from typing import Dict, Optional, Tuple


def export_mongodb_data(
        uri: str,
        db: str,
        collection: str,
        output_file: str,
        query: Optional[Dict] = None,
        fields: Optional[str] = None,
        export_format: str = "json"
) -> Tuple[bool, str]:
    """
    导出MongoDB数据到文件（兼容mongoimport导入格式）

    参数:
    uri: MongoDB连接字符串 (e.g. "mongodb://user:pass@localhost:27017")
    db: 数据库名称
    collection: 集合名称
    output_file: 输出文件路径
    query: 导出数据的查询条件 (e.g. {"age": {"$gt": 25}})
    fields: 指定导出字段 (e.g. "name,age,email")
    export_format: 导出格式 ("json" 或 "csv")
    """
    # 构建基础命令
    cmd = [
        "mongoexport",
        f"--uri={uri}",
        f"--db={db}",
        f"--collection={collection}",
        f"--out={output_file}"
    ]

    # 添加格式参数
    if export_format.lower() == "csv":
        cmd.append("--type=csv")
        if not fields:
            raise ValueError("导出CSV格式时必须指定--fields参数")

    # 添加查询条件
    if query:
        cmd.append(f"--query='{json.dumps(query)}'")

    # 添加字段选择
    if fields:
        cmd.append(f"--fields={fields}")

    # 执行导出命令
    try:
        result = subprocess.run(
            " ".join(cmd),
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ 导出成功!")
        print(f"📁 文件路径: {output_file}")
        print(f"📊 导出格式: {export_format.upper()}")
        if query:
            print(f"🔍 查询条件: {json.dumps(query)}")
        return True, "Export successful"
    except subprocess.CalledProcessError as e:
        print(f"❌ 导出失败: {e.stderr}")
        return False, f"Export failed: {e.stderr}"
    except FileNotFoundError:
        print("❌ 未找到mongoexport工具，请安装MongoDB数据库工具")
        return False, "mongoexport tool not found, please install MongoDB database tools"


if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="MongoDB数据导出工具")
    parser.add_argument("--uri", required=True, help="MongoDB连接URI")
    parser.add_argument("--db", required=True, help="数据库名称")
    parser.add_argument("--collection", required=True, help="集合名称")
    parser.add_argument("--output", required=True, help="输出文件路径")
    parser.add_argument("--query", type=json.loads, help="查询条件(JSON格式)")
    parser.add_argument("--fields", help="导出字段(逗号分隔)")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="导出格式")

    args = parser.parse_args()

    # 执行导出
    export_mongodb_data(
        uri=args.uri,
        db=args.db,
        collection=args.collection,
        output_file=args.output,
        query=args.query,
        fields=args.fields,
        export_format=args.format
    )
