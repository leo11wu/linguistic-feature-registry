import SwiftUI

struct AnalysisChoicesView:View {
    @EnvironmentObject var model:AppModel
    private func metadataPicker(_ title:String,selection:Binding<String>,empty:String)->some View {
        Picker(title,selection:selection) {
            Text(empty).tag("")
            ForEach(model.metadataColumns,id:\.self) {Text($0).tag($0)}
        }
    }
    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            Group {
            Divider()
            Text("参照、配对与构图").font(.headline)
            metadataPicker("语料层统计",selection:$model.corpusGroupColumn,empty:"所有目标文本合并")
            Picker("参照语料",selection:$model.referenceMode) {
                Text("本批目标文本").tag("batch")
                Text("已有提取结果（冻结参照）").tag("external")
            }
            if model.referenceMode=="external" {
                Button("选择参照结果目录"){model.chooseReference()}
                Text(model.referencePath.isEmpty ? "尚未选择参照" : model.referencePath).font(.caption).foregroundColor(.secondary).lineLimit(2)
                Text("使用参照建立时的分块。词形/lemma须匹配；目标文本不参与重建参照。").font(.caption).foregroundColor(.secondary)
            } else {
                metadataPicker("离散度分块",selection:$model.partitionColumn,empty:"每篇文本一块")
                Text("搭配与词块使用同一统计组的全部文本；JS散度以组内其余文本为参照。").font(.caption).foregroundColor(.secondary)
            }
            metadataPicker("配对编号列",selection:$model.pairColumn,empty:"未设置")
            Text("LSM需每个非空编号恰好两篇文本；每对输出一行，不重复写入文档特征。").font(.caption).foregroundColor(.secondary)
            }
            if model.selected.contains("MWE05") {
                DisclosureGroup("词块发现条件") {
                    Stepper("词块长度：\(model.bundleOrder)",value:$model.bundleOrder,in:2...4)
                    Stepper("参照最低频次：\(model.bundleFrequency)",value:$model.bundleFrequency,in:1...100000)
                    Stepper("至少出现于 \(model.bundleDocuments) 篇参照文档",value:$model.bundleDocuments,in:1...10000)
                }
            }
            if model.selected.contains(where:{$0.hasPrefix("NET")}) {
                GroupBox("网络定义") {
                    VStack(alignment:.leading,spacing:8) {
                        Picker("边的含义",selection:$model.networkEdge) {Text("句内相邻词").tag("adjacent");Text("句内窗口共现").tag("window")}
                        if model.networkEdge=="window" {Stepper("最大词距：\(model.networkWindow)",value:$model.networkWindow,in:1...20)}
                        Toggle("有向图（按文本先后）",isOn:$model.networkDirected)
                        Stepper("边最低出现次数：\(model.networkMinCount)",value:$model.networkMinCount,in:1...10000)
                        Text("节点使用当前词形/lemma。路径与聚类按二值图；出现次数另存为强度。排除自环，保留孤立节点。").font(.caption).foregroundColor(.secondary)
                    }.padding(4)
                }
            }
        }
    }
}
