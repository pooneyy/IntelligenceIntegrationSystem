# ====== 测试脚本 ======
from Tools.CrawlStatistics import CrawlStatistics

if __name__ == "__main__":
    print("==== 测试CrawlStatistics增强功能 ====")

    # 创建实例
    stats = CrawlStatistics()

    # 测试1: 基本计数器功能
    print("\n测试1: 基本计数器功能")
    stats.counter_log(["domain1"], "pages_crawled")
    stats.counter_log(["domain1", "page1"], "images_found")
    stats.counter_log(["domain1", "page1"], "links_found")
    stats.counter_log(["domain1", "page1"], "links_found")  # 增加计数
    stats.counter_log(["domain1", "page2"], "videos_found")

    # 验证计数器
    assert stats.get_classified_counter(["domain1"]) == {"pages_crawled": 1}
    assert stats.get_classified_counter(["domain1", "page1"]) == {"images_found": 1, "links_found": 2}

    # 测试2: 子项日志功能
    print("\n测试2: 子项日志功能")
    stats.sub_item_log(["domain1", "page1"], "image1.jpg", "success")
    stats.sub_item_log(["domain1", "page1"], "image2.png", "failed")
    stats.sub_item_log(["domain1", "page1"], "image3.gif", "success")
    stats.sub_item_log(["domain1", "page2"], "video1.mp4", "success")

    # 验证子项
    page1_items = stats.get_sub_item_statistics(["domain1", "page1"])
    assert len(page1_items["success"]) == 2
    assert "image1.jpg" in page1_items["success"]
    assert len(page1_items["failed"]) == 1

    # 测试3: 多层嵌套命名空间
    print("\n测试3: 多层嵌套命名空间")
    stats.counter_log(["domain2", "section1", "subsectionA"], "widgets_processed")
    stats.counter_log(["domain2", "section1", "subsectionA"], "widgets_processed")
    stats.counter_log(["domain2", "section1", "subsectionB"], "errors")
    stats.sub_item_log(["domain2", "section1", "subsectionA"], "widget-001", "ok")
    stats.sub_item_log(["domain2", "section1", "subsectionA"], "widget-002", "defect")
    stats.sub_item_log(["domain2", "section1", "subsectionB"], "widget-003", "pending")

    # 测试4: dump全部统计信息
    print("\n测试4: dump全部统计信息")
    full_dump = stats.dump()
    print("完整转储输出:")
    print(full_dump)

    # 验证关键项存在
    assert "domain1" in full_dump
    assert "page1" in full_dump
    assert "section1" in full_dump
    assert "widgets_processed" in full_dump
    assert "widget-001" in full_dump

    # 测试5: 按命名空间dump
    print("\n测试5: 按命名空间dump")
    print("转储domain1:")
    domain1_dump = stats.dump(["domain1"])
    print(domain1_dump)

    # 验证内容
    assert "page1" in domain1_dump
    assert "images_found" in domain1_dump
    assert "image1.jpg" in domain1_dump
    # 验证非domain1内容不包含
    assert "domain2" not in domain1_dump
    assert "widgets_processed" not in domain1_dump

    # 测试6: 重置特定命名空间
    print("\n测试6: 重置特定命名空间")
    print("重置前domain1/page1:", stats.get_classified_counter(["domain1", "page1"]))
    stats.reset(["domain1", "page1"])
    print("重置后domain1/page1:", stats.get_classified_counter(["domain1", "page1"]))

    # 验证重置效果
    assert stats.get_classified_counter(["domain1", "page1"]) == {}
    assert stats.get_sub_item_statistics(["domain1", "page1"]) == {}
    # 验证其他命名空间保持不变
    assert stats.get_classified_counter(["domain1"]) != {}
    assert stats.get_classified_counter(["domain1", "page2"]) != {}
    assert stats.get_classified_counter(["domain2", "section1", "subsectionA"]) != {}

    # 测试7: 重置父命名空间（包括子空间）
    print("\n测试7: 重置父命名空间")
    print("重置domain2前计数器:", stats.get_classified_counter(["domain2", "section1", "subsectionA"]))
    stats.reset(["domain2"])
    print("重置domain2后计数器:", stats.get_classified_counter(["domain2", "section1", "subsectionA"]))

    # 验证整个domain2被清除
    assert stats.get_classified_counter(["domain2", "section1", "subsectionA"]) == {}
    assert stats.get_sub_item_statistics(["domain2", "section1", "subsectionA"]) == {}
    # 验证domain1保持不变
    assert stats.get_classified_counter(["domain1"]) != {}

    # 测试8: 完全重置
    print("\n测试8: 完全重置")
    stats.reset()
    full_dump_after_reset = stats.dump()
    print("完全重置后dump:", full_dump_after_reset)

    # 验证所有数据被清除
    assert stats.get_classified_counter(["domain1"]) == {}
    assert stats.get_classified_counter(["domain1", "page2"]) == {}
    assert full_dump_after_reset == ""

    # 测试9: 复杂dump场景
    print("\n测试9: 复杂dump场景")
    # 添加复杂数据
    stats.counter_log(["api", "v1", "users"], "requests", )
    stats.counter_log(["api", "v1", "users"], "requests", )  # 2次
    stats.counter_log(["api", "v1", "products"], "requests")
    stats.counter_log(["api", "v2", "users"], "requests")
    stats.sub_item_log(["api", "v1", "users"], "user-001", "success")
    stats.sub_item_log(["api", "v1", "users"], "user-002", "failed")
    stats.sub_item_log(["api", "v1", "products"], "product-001", "success")

    # 转储特定层级
    print("API v1 转储:")
    api_v1_dump = stats.dump(["api", "v1"])
    print(api_v1_dump)

    # 验证内容格式
    assert "v1" in api_v1_dump
    assert "users" in api_v1_dump
    assert "requests: 2" in api_v1_dump  # 计数器值
    assert "STATUS: success (Count: 1)" in api_v1_dump
    assert "user-001" in api_v1_dump
    # 验证v2内容不包含
    assert "v2" not in api_v1_dump

    # 测试10: 空命名空间处理
    print("\n测试10: 空命名空间处理")
    empty_dump = stats.dump(["nonexistent"])
    print("空命名空间转储:", empty_dump)
    assert "" in empty_dump

    # 测试11: 重置子命名空间
    print("\n测试11: 重置子命名空间")
    stats.reset(["api", "v1", "users"])
    users_dump = stats.dump(["api", "v1", "users"])
    print("重置后的用户命名空间:", users_dump)
    assert "" in users_dump
    # 验证兄弟命名空间仍然存在
    assert stats.get_classified_counter(["api", "v1", "products"]) != {}

    print("\n==== 所有测试通过! ====")
