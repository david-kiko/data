from ltp import LTP

# 初始化LTP模型
ltp = LTP("LTP/base")

# 测试文本
text = "工作中心有多少制造任务"

# 使用pipeline进行分词、词性标注、命名实体识别和依存句法分析
output = ltp.pipeline([text], tasks=["cws", "pos", "ner", "sdp"])

# 打印输出结果
print("分词结果:", output.cws[0])
print("词性标注:", output.pos[0])
print("命名实体:", output.ner[0])
print("依存句法:", output.sdp[0]) 