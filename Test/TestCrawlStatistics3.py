from Tools.CrawlStatistics import CrawlStatistics


def test_sub_item_limit():
    """测试子项日志数量限制功能"""
    # 初始化单例（需先重置）
    CrawlStatistics._instance = None
    cs = CrawlStatistics()
    cs.set_sub_items_limit(3)  # 设置全局限制为3

    # 场景1: 基础限制功能 - 不超过限制时保留全部数据
    print("\n=== 场景1: 基础限制功能测试 ===")
    cs.sub_item_log(["test"], "item1", "success")
    cs.sub_item_log(["test"], "item2", "failed")
    cs.sub_item_log(["test"], "item3", "pending")
    stats = cs.get_sub_item_statistics(["test"])
    assert len(stats["success"]) == 1, "成功状态应保留1项"
    assert len(stats["failed"]) == 1, "失败状态应保留1项"
    assert len(stats["pending"]) == 1, "等待状态应保留1项"
    print("✅ 场景1通过：3项数据完整保留")

    # 场景2: FIFO删除 - 超过限制时删除最旧条目
    print("\n=== 场景2: FIFO删除测试 ===")
    cs.sub_item_log(["fifo"], "old_success", "success")  # 应被删除
    cs.sub_item_log(["fifo"], "keep_failed", "failed")
    cs.sub_item_log(["fifo"], "keep_pending", "pending")
    cs.sub_item_log(["fifo"], "new_success", "success")  # 触发删除

    stats = cs.get_sub_item_statistics(["fifo"])
    assert "old_success" not in stats.get("success", []), "最旧项应被删除"
    assert "keep_failed" in stats["failed"], "第二项应保留"
    assert "keep_pending" in stats["pending"], "第三项应保留"
    assert "new_success" in stats["success"], "最新项应保留"
    print("✅ 场景2通过：FIFO删除机制生效")

    # 场景3: 混合状态删除 - 按添加顺序而非状态删除
    print("\n=== 场景3: 混合状态删除测试 ===")
    sequence = [
        ("A", "success"),  # 应被删除
        ("B", "failed"),
        ("C", "success"),  # 应被删除
        ("D", "pending"),
        ("E", "failed")
    ]
    for item, status in sequence:
        cs.sub_item_log(["mixed"], item, status)

    stats = cs.get_sub_item_statistics(["mixed"])
    assert "A" not in stats.get("success", []), "首项应被删除"
    assert "B" not in stats["failed"], "第三项应保留"
    assert "C" in stats.get("success", []), "第二项应被删除"
    assert "D" in stats["pending"], "第四项应保留"
    assert "E" in stats["failed"], "第五项应保留"
    print("✅ 场景3通过：混合状态删除顺序正确")

    # 场景4: 命名空间隔离 - 不同空间独立计数
    print("\n=== 场景4: 命名空间隔离测试 ===")
    cs.sub_item_log(["ns1"], "A", "success")
    cs.sub_item_log(["ns1"], "B", "failed")
    cs.sub_item_log(["ns1"], "C", "pending")  # ns1达到限制
    cs.sub_item_log(["ns2"], "X", "success")  # ns2未达限制

    stats_ns1 = cs.get_sub_item_statistics(["ns1"])
    stats_ns2 = cs.get_sub_item_statistics(["ns2"])
    assert sum(len(v) for v in stats_ns1.values()) == 3, "ns1应保留3项"
    assert sum(len(v) for v in stats_ns2.values()) == 1, "ns2应保留1项"
    print("✅ 场景4通过：命名空间隔离生效")

    # 场景5: 重置后限制功能
    print("\n=== 场景5: 重置后限制测试 ===")
    cs.reset(["mixed"])  # 重置场景3的命名空间
    cs.sub_item_log(["mixed"], "new1", "pending")
    cs.sub_item_log(["mixed"], "new2", "success")
    cs.sub_item_log(["mixed"], "new3", "failed")
    cs.sub_item_log(["mixed"], "new4", "pending")  # 触发删除

    stats = cs.get_sub_item_statistics(["mixed"])
    assert "new1" not in stats["pending"], "重置后首项应被删除"
    assert len(stats["pending"]) == 1, "pending状态应保留最新项"
    print("✅ 场景5通过：重置后限制功能正常")

    # 场景6: 零限制处理
    print("\n=== 场景6: 零限制测试 ===")
    cs.set_sub_items_limit(0)
    cs.sub_item_log(["zero"], "test_item", "success")
    stats = cs.get_sub_item_statistics(["zero"])
    assert stats == {}, "零限制时应无数据保留"
    print("✅ 场景6通过：零限制处理正确")

    print("\n=== 所有测试通过 ===")


if __name__ == "__main__":
    test_sub_item_limit()
