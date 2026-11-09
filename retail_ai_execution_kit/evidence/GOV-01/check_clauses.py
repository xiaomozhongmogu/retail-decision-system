"""GOV-01 条款核对：直接从课程原件抽取文本，逐条检查关键条款是否存在于原件和提取文本中。
用法（项目根目录）：python3 -I evidence/GOV-01/check_clauses.py
依赖：Python 标准库；.doc 转换使用 macOS 自带 textutil。只读，不修改任何文件。"""
import re,sys,json,zipfile,html,subprocess,tempfile,os
def docx_text(p):
    x=zipfile.ZipFile(p).read('word/document.xml').decode('utf8')
    x=re.sub(r'</w:p>','\n',x); x=re.sub(r'<w:tab/>','\t',x); x=re.sub(r'<[^>]+>','',x)
    return html.unescape(x)
def doc_text(p):
    with tempfile.TemporaryDirectory() as d:
        out=os.path.join(d,'t.txt')
        subprocess.run(['textutil','-convert','txt','-output',out,p],check=True)
        return open(out,encoding='utf8').read()
def norm(s): return re.sub(r'\s+','',s)
course_orig=norm(docx_text('sources/course_guide_2026.docx'))
course_ext=norm(open('sources/course_guide_extracted.txt',encoding='utf8').read())
topic_orig=norm(doc_text('sources/topic_report_template.doc'))
topic_ext=norm(open('sources/topic_report_extracted.txt',encoding='utf8').read())
course=[
 ("COURSE二 时效","以上数据集需选择2026年1月以后的数据集"),
 ("COURSE三(一) 天池表时效","需2025年6月后的数据集"),
 ("COURSE三(一) 规模","要求数据规模不少于1万条记录或10MB数据,数据维度不少于8个字段,且数据应具有时间维度"),
 ("COURSE二 人数","本次实习采用4-6人小组形式"),
 ("COURSE三(一) 合规","实验数据仅限于教学使用,不得用于商业用途或对外发布"),
 ("COURSE三(三)2 数仓可选","数据仓库建模（可选）"),
 ("COURSE三(六) 标题选做","AI智能处理模块【选做，加分项】"),
 ("COURSE三(六) 至少1","要求学生必须完成至少1个AI智能子模块"),
 ("COURSE三(六) 加权5分","总分加权5分,可超过100分上限计分(最高110分)"),
 ("COURSE三(六)8 方向1-2","各小组从以下方向中至少选择1-2个完整实现"),
 ("COURSE三(六)6 合成数据","当真实数据不足或涉及隐私时,可以使用AI生成合成数据用于训练和测试"),
 ("COURSE五(一) 40%","商务智能与数据挖掘设计方案(占40%)"),
 ("COURSE五(一) 九项-需求","某行业的决策支持需求分析"),
 ("COURSE五(一) 九项-采集可选","数据采集方案(可选)"),
 ("COURSE五(一) 九项-实现步骤","②-⑦方案的具体实现步骤(可附关键代码)"),
 ("COURSE五(一) 九项-反思","设计体会与反思"),
 ("COURSE五(二) 40%","系统实现与演示(占40%)"),
 ("COURSE五(二) 10分钟","并进行10分钟现场演示"),
 ("COURSE五(二) 每人1-2问","回答评委提问(每人1-2个问题)"),
 ("COURSE五(三) 20%","团队协作与个人贡献(占20%)"),
 ("COURSE五(四) 正文第2项","查阅10篇以上文献,有创新点"),
 ("COURSE五(四) 正文第6项","至少2个AI子模块,有实际应用价值"),
 ("COURSE五(四) 正文第9项","数据可视化合理美观"),
 ("COURSE五(四) 正文第10项","综合总体印象分|项目完成度、汇报表现"),
 ("COURSE五 加分1","完成3个以上AI子模块,且全部达到生产可用水平:+3分"),
 ("COURSE五 加分封顶","加分项(最高加10分,超过100分上限)"),
 ("COURSE六 4周","总计4周"),
 ("COURSE附录 评分8难度","8、综合实习有一定的设计和实现难度,并且需要一定的时间来积累技术和专业知识"),
 ("COURSE附录 评分9","9、数据分析的内容合理恰当,方便用户使用理解主题"),
 ("COURSE附录 评分10","10、数据分析结果可视化合理,综合实习的综合总体印象分"),
 ("COURSE附录 评分6","6、AI智能处理模块完整性与创新性(至少2个子模块)"),
 ("COURSE附录 评分3","3、课程设计文档能够简明扼要的反映主要的综合实践模块,包括数据采集、数据处理、数据分析等"),
 ("COURSE附录 六章-1","一、实验目的"),("COURSE附录 六章-2","二、实验设备和环境"),
 ("COURSE附录 六章-3","三、实验内容及要求"),("COURSE附录 六章-4","四、实验步骤"),
 ("COURSE附录 步骤截图","每个步骤要有截图或代码片段佐证"),
 ("COURSE附录 六章-5","五、实验中的问题处理及分析"),("COURSE附录 六章-6","六、实验总结"),
]
topic=[
 ("TOPIC 一","一、选题的目的和意义"),("TOPIC 二","二、选题背景分析（文献综述，要列出参考文献）"),
 ("TOPIC 三","三、选题研究的内容"),("TOPIC 四","四、选题研究的研究方法和解决的主要问题"),("TOPIC 五","五、课程实习计划"),
 ("TOPIC 阶段1","2026年10月23日至2026年11月9日：搜集相关商务智能与数据挖掘主题数据并进行预处理；完成数据选题、数据预处理；并提交选题报告"),
 ("TOPIC 阶段2","2026年11月10日至2026年11月30日：围绕主题分析的模型设计与数据分析；并提交中期检查报告；并现场答辩"),
 ("TOPIC 阶段3","2026年12月1日至2026年12月22日：围绕主题分析的商务智能与数据挖掘应用；提交课程报告正式稿；并现场答辩"),
 ("TOPIC 日期","日期：2026年11月9日"),
]
rows=[];fail=0
for lab,ph in course:
  p=norm(ph).replace('|','')
  # table cells joined differently; test both with and without separator
  o=p in course_orig or norm(ph.split('|')[0]) in course_orig
  e=p in course_ext or norm(ph.replace('|','|')) in course_ext or norm(ph.split('|')[0]) in course_ext
  rows.append((lab,o,e)); fail+= (not o)
for lab,ph in topic:
  p=norm(ph); o=p in topic_orig; e=p in topic_ext; rows.append((lab,o,e)); fail+=(not o)
for r in rows: print(('OK ' if r[1] else 'MISS'), 'orig=%s ext=%s'%(r[1],r[2]), r[0])
print(json.dumps({"checked":len(rows),"missing_in_original":fail}))
ext_miss=sum(1 for r in rows if not r[2])
print(json.dumps({'missing_in_extracted':ext_miss}))
sys.exit(1 if fail or ext_miss else 0)

