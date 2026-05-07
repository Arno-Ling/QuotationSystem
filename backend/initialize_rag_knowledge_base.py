"""
ChromaDB Initialization Script for Exception Agent RAG Knowledge Base

This script initializes the ChromaDB collection for historical exception cases
and loads sample cases to bootstrap the knowledge base.

Usage:
    python initialize_rag_knowledge_base.py
"""

import chromadb
from chromadb.config import Settings
import json
import os
from datetime import datetime
from typing import List, Dict


def get_chroma_client(persist_directory: str = "./chroma_db/exception_agent"):
    """
    Initialize and return ChromaDB client with persistence.
    
    Args:
        persist_directory: Directory path for ChromaDB persistence
        
    Returns:
        ChromaDB client instance
    """
    # Create directory if it doesn't exist
    os.makedirs(persist_directory, exist_ok=True)
    
    # Initialize ChromaDB client with persistence
    client = chromadb.PersistentClient(
        path=persist_directory,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    
    return client


def initialize_collection(client: chromadb.Client, collection_name: str = "exception_cases"):
    """
    Initialize or get the exception cases collection.
    
    Args:
        client: ChromaDB client instance
        collection_name: Name of the collection
        
    Returns:
        ChromaDB collection instance
    """
    # Try to get existing collection, or create new one
    try:
        collection = client.get_collection(name=collection_name)
        print(f"✓ Found existing collection '{collection_name}'")
    except Exception:
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "Historical exception cases for RAG retrieval"}
        )
        print(f"✓ Created new collection '{collection_name}'")
    
    return collection


def load_sample_cases() -> List[Dict]:
    """
    Load sample historical exception cases.
    
    Returns:
        List of sample exception case dictionaries
    """
    sample_cases = [
        {
            "id": "case_001",
            "exception_type": "尺寸偏差",
            "description": "注塑件外径尺寸偏大0.5mm，超出公差范围±0.2mm。检测发现整批50件均存在此问题。",
            "material": "ABS塑料",
            "process_type": "注塑成型",
            "root_cause": "模具温度过高导致材料膨胀，冷却时间不足",
            "responsible_party": "supplier",
            "resolution": "调整模具温度从220°C降至200°C，延长冷却时间从15秒增加到25秒，重新生产合格品",
            "outcome": "成功解决，后续批次尺寸合格率100%",
            "resolution_date": "2024-01-15",
            "cost_impact": 8500.0,
            "time_impact_days": 5
        },
        {
            "id": "case_002",
            "exception_type": "表面缺陷",
            "description": "铸件表面出现气孔和砂眼，影响外观质量。缺陷集中在顶部区域，约占表面积的15%。",
            "material": "铝合金A356",
            "process_type": "压铸",
            "root_cause": "浇注温度过低，排气不畅，砂型含水量过高",
            "responsible_party": "supplier",
            "resolution": "提高浇注温度至680°C，改进排气系统，严格控制砂型含水量<3%，增加质检频次",
            "outcome": "缺陷率从15%降至2%，符合验收标准",
            "resolution_date": "2024-02-20",
            "cost_impact": 12000.0,
            "time_impact_days": 7
        },
        {
            "id": "case_003",
            "exception_type": "材料问题",
            "description": "钢板硬度不足，实测HRC 35，要求HRC 42-45。整批材料均不合格。",
            "material": "45号钢",
            "process_type": "热处理",
            "root_cause": "材料供应商提供的钢材含碳量不足，淬火工艺参数不当",
            "responsible_party": "material_vendor",
            "resolution": "退回不合格材料，要求供应商提供材质证明和光谱分析报告，更换合格材料重新生产",
            "outcome": "更换材料后硬度达标，供应商承担全部损失",
            "resolution_date": "2024-03-10",
            "cost_impact": 25000.0,
            "time_impact_days": 14
        },
        {
            "id": "case_004",
            "exception_type": "组装问题",
            "description": "轴承座与轴配合过紧，无法正常装配。检查发现孔径偏小0.3mm。",
            "material": "铸铁HT200",
            "process_type": "机械加工",
            "root_cause": "加工中心刀具磨损未及时更换，导致孔径尺寸偏小",
            "responsible_party": "supplier",
            "resolution": "使用铰刀修正孔径至标准尺寸，更换磨损刀具，加强刀具管理和定期检测",
            "outcome": "修正后装配顺利，建立刀具寿命管理制度",
            "resolution_date": "2024-01-25",
            "cost_impact": 3500.0,
            "time_impact_days": 3
        },
        {
            "id": "case_005",
            "exception_type": "表面缺陷",
            "description": "喷涂表面出现流挂和橘皮现象，影响产品外观。缺陷面积约30%。",
            "material": "钢板Q235",
            "process_type": "喷涂",
            "root_cause": "喷涂粘度过低，喷枪距离过近，环境湿度过高",
            "responsible_party": "supplier",
            "resolution": "调整涂料粘度至18-22秒（涂-4杯），规范喷枪距离为20-25cm，控制车间湿度<70%，返工重新喷涂",
            "outcome": "返工后外观合格，建立喷涂工艺标准作业指导书",
            "resolution_date": "2024-02-05",
            "cost_impact": 6800.0,
            "time_impact_days": 4
        },
        {
            "id": "case_006",
            "exception_type": "尺寸偏差",
            "description": "CNC加工的螺纹孔深度不足，实测深度18mm，图纸要求20mm±0.5mm。",
            "material": "不锈钢304",
            "process_type": "CNC加工",
            "root_cause": "编程时Z轴深度参数设置错误，操作员未进行首件检验",
            "responsible_party": "supplier",
            "resolution": "修正CNC程序，对已加工件进行深度补加工，强化首件三检制度",
            "outcome": "补加工后全部合格，更新程序库并加强培训",
            "resolution_date": "2024-03-01",
            "cost_impact": 4200.0,
            "time_impact_days": 2
        },
        {
            "id": "case_007",
            "exception_type": "材料问题",
            "description": "橡胶密封圈老化开裂，使用不到设计寿命的50%。",
            "material": "丁腈橡胶NBR",
            "process_type": "橡胶成型",
            "root_cause": "材料配方中抗氧剂含量不足，存储环境温度过高加速老化",
            "responsible_party": "material_vendor",
            "resolution": "要求供应商改进配方增加抗氧剂，改善存储条件（温度<25°C，避光），更换全部密封圈",
            "outcome": "新配方密封圈性能稳定，寿命达到设计要求",
            "resolution_date": "2024-02-28",
            "cost_impact": 15000.0,
            "time_impact_days": 10
        },
        {
            "id": "case_008",
            "exception_type": "组装问题",
            "description": "电机与减速器连接时出现同心度偏差，振动超标。",
            "material": "铸铁+钢",
            "process_type": "机械装配",
            "root_cause": "装配基准面不平整，紧固螺栓力矩不均匀，缺少找正工具",
            "responsible_party": "internal",
            "resolution": "重新加工基准面保证平面度，使用扭力扳手按规定力矩紧固，配备激光对中仪进行找正",
            "outcome": "同心度偏差控制在0.05mm以内，振动值合格",
            "resolution_date": "2024-01-18",
            "cost_impact": 5500.0,
            "time_impact_days": 3
        },
        {
            "id": "case_009",
            "exception_type": "表面缺陷",
            "description": "焊接接头出现裂纹和气孔，X射线探伤不合格。",
            "material": "碳钢Q345B",
            "process_type": "焊接",
            "root_cause": "焊接电流过大，焊接速度过快，焊前未充分预热，焊条受潮",
            "responsible_party": "supplier",
            "resolution": "降低焊接电流至合理范围，控制焊接速度，焊前预热至150°C，使用烘干焊条，返修焊缝",
            "outcome": "返修后探伤合格，建立焊接工艺评定记录",
            "resolution_date": "2024-03-15",
            "cost_impact": 18000.0,
            "time_impact_days": 8
        },
        {
            "id": "case_010",
            "exception_type": "尺寸偏差",
            "description": "齿轮齿距累积误差超差，实测0.15mm，标准要求≤0.08mm。",
            "material": "合金钢40Cr",
            "process_type": "齿轮加工",
            "root_cause": "滚齿机分度蜗轮磨损，机床精度下降",
            "responsible_party": "supplier",
            "resolution": "维修滚齿机更换分度蜗轮，重新进行机床精度校准，对不合格齿轮进行报废处理",
            "outcome": "机床精度恢复，后续齿轮加工精度稳定",
            "resolution_date": "2024-02-12",
            "cost_impact": 22000.0,
            "time_impact_days": 12
        },
        {
            "id": "case_011",
            "exception_type": "材料问题",
            "description": "塑料件在低温环境下脆裂，冲击强度不足。",
            "material": "聚丙烯PP",
            "process_type": "注塑成型",
            "root_cause": "材料牌号选择不当，未使用耐低温改性PP，回料添加比例过高",
            "responsible_party": "internal",
            "resolution": "更换为耐低温PP材料，严格控制回料比例≤15%，增加低温冲击测试",
            "outcome": "更换材料后低温性能满足要求，通过-20°C冲击测试",
            "resolution_date": "2024-01-30",
            "cost_impact": 11000.0,
            "time_impact_days": 6
        },
        {
            "id": "case_012",
            "exception_type": "组装问题",
            "description": "液压缸装配后出现内泄漏，压力保持不住。",
            "material": "合金钢+密封件",
            "process_type": "液压装配",
            "root_cause": "活塞密封圈安装时损伤，缸筒内壁有划痕，装配间隙过大",
            "responsible_party": "supplier",
            "resolution": "更换密封圈并规范安装流程，研磨缸筒内壁消除划痕，严格控制装配间隙，增加气密性测试",
            "outcome": "泄漏问题解决，压力保持稳定，建立液压件装配规范",
            "resolution_date": "2024-03-05",
            "cost_impact": 9500.0,
            "time_impact_days": 5
        }
    ]
    
    return sample_cases


def add_cases_to_collection(collection: chromadb.Collection, cases: List[Dict]):
    """
    Add historical cases to ChromaDB collection.
    
    Args:
        collection: ChromaDB collection instance
        cases: List of case dictionaries
    """
    # Prepare data for batch insertion
    ids = []
    documents = []
    metadatas = []
    
    for case in cases:
        # Create document text for embedding (description + resolution)
        document_text = f"{case['description']} {case['resolution']}"
        
        # Prepare metadata (all fields except description and resolution)
        metadata = {
            "exception_type": case["exception_type"],
            "material": case["material"],
            "process_type": case["process_type"],
            "root_cause": case["root_cause"],
            "responsible_party": case["responsible_party"],
            "resolution": case["resolution"],
            "outcome": case["outcome"],
            "resolution_date": case["resolution_date"],
            "cost_impact": case["cost_impact"],
            "time_impact_days": case["time_impact_days"]
        }
        
        ids.append(case["id"])
        documents.append(document_text)
        metadatas.append(metadata)
    
    # Add to collection
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print(f"✓ Added {len(cases)} cases to collection")


def verify_collection(collection: chromadb.Collection):
    """
    Verify collection by running test queries.
    
    Args:
        collection: ChromaDB collection instance
    """
    print("\n=== Verification Tests ===")
    
    # Test 1: Count total cases
    count = collection.count()
    print(f"✓ Total cases in collection: {count}")
    
    # Test 2: Query for dimension deviation cases
    results = collection.query(
        query_texts=["尺寸偏差 加工精度"],
        n_results=3
    )
    print(f"✓ Query test (尺寸偏差): Found {len(results['ids'][0])} relevant cases")
    
    # Test 3: Query for surface defect cases
    results = collection.query(
        query_texts=["表面缺陷 气孔"],
        n_results=3
    )
    print(f"✓ Query test (表面缺陷): Found {len(results['ids'][0])} relevant cases")
    
    # Test 4: Query for material issues
    results = collection.query(
        query_texts=["材料问题 硬度不足"],
        n_results=3
    )
    print(f"✓ Query test (材料问题): Found {len(results['ids'][0])} relevant cases")
    
    print("\n✓ All verification tests passed!")


def main():
    """
    Main function to initialize RAG knowledge base.
    """
    print("=== ChromaDB Initialization for Exception Agent ===\n")
    
    # Step 1: Initialize ChromaDB client
    print("Step 1: Initializing ChromaDB client...")
    persist_dir = os.getenv("CHROMA_DB_PATH", "./chroma_db/exception_agent")
    client = get_chroma_client(persist_directory=persist_dir)
    
    # Step 2: Initialize collection
    print("\nStep 2: Initializing collection...")
    collection = initialize_collection(client, collection_name="exception_cases")
    
    # Step 3: Check if collection already has data
    existing_count = collection.count()
    if existing_count > 0:
        print(f"\n⚠ Collection already contains {existing_count} cases")
        response = input("Do you want to reset and reload? (yes/no): ")
        if response.lower() == 'yes':
            client.delete_collection(name="exception_cases")
            collection = initialize_collection(client, collection_name="exception_cases")
            print("✓ Collection reset")
        else:
            print("✓ Keeping existing data")
            verify_collection(collection)
            return
    
    # Step 4: Load sample cases
    print("\nStep 3: Loading sample cases...")
    sample_cases = load_sample_cases()
    print(f"✓ Loaded {len(sample_cases)} sample cases")
    
    # Step 5: Add cases to collection
    print("\nStep 4: Adding cases to collection...")
    add_cases_to_collection(collection, sample_cases)
    
    # Step 6: Verify collection
    print("\nStep 5: Verifying collection...")
    verify_collection(collection)
    
    print("\n=== Initialization Complete ===")
    print(f"ChromaDB path: {persist_dir}")
    print(f"Collection name: exception_cases")
    print(f"Total cases: {collection.count()}")


if __name__ == "__main__":
    main()
