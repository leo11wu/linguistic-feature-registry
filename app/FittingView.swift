import SwiftUI

struct FitTable:Identifiable {
    let id,label,unit:String
    init(_ d:[String:Any]) {id=d["id"] as? String ?? "";label=d["label"] as? String ?? "";unit=d["unit"] as? String ?? ""}
}

struct FittingView:View {
    @EnvironmentObject var model:AppModel
    @State private var showReport=false
    let showResources:()->Void
    let modelNames:[(String,String,String)]=[
        ("linear","线性关系","relation"),("power","幂函数（原尺度）","relation"),("power_log","幂函数（对数回归）","relation"),("exponential","指数关系","relation"),
        ("zipf","Zipf","relation"),("zipf_mandelbrot","Zipf–Mandelbrot","relation"),("heaps","Heaps","relation"),
        ("menzerath_altmann","Menzerath–Altmann","relation"),("pearson","Pearson 相关","relation"),("spearman","Spearman 秩相关","relation"),
        ("poisson","泊松（含零）","distribution"),("zero_truncated_poisson","零截断泊松","distribution"),
        ("geometric","几何（从1开始）","distribution"),("negative_binomial","负二项（含零）","distribution"),
        ("lnre_fzm","LNRE：fZM","distribution"),("lnre_zm","LNRE：ZM","distribution"),("lnre_gigp","LNRE：GIGP","distribution")]
    private func columnPicker(_ title:String,selection:Binding<String>,optional:String?=nil)->some View {
        Picker(title,selection:selection) {
            if let optional=optional {Text(optional).tag("")}
            else if selection.wrappedValue.isEmpty {Text("请选择").tag("")}
            ForEach(model.fitColumns,id:\.self){Text($0).tag($0)}
        }
    }
    private var needsSciPy:Bool {model.fitModels.contains(where:{$0 != "linear" && $0 != "power_log" && !$0.hasPrefix("lnre_")}) && !model.resources.contains(where:{$0.id=="corpus" && $0.installed})}
    var body:some View {
        HStack(alignment:.top,spacing:24) {
            ScrollView {
                VStack(alignment:.leading,spacing:14) {
                    Text("1  复用测量数据").font(.headline)
                    HStack {Button("选择提取结果"){model.chooseFitSource(folder:true)};Button("导入CSV"){model.chooseFitSource(folder:false)}}
                    Text(model.fitSource.isEmpty ? "先选择已有提取结果，无须重新解析文本。" : model.fitSource).font(.caption).foregroundColor(.secondary).lineLimit(3)
                    if !model.fitTables.isEmpty {
                        Picker("观测表",selection:Binding(get:{model.fitTable},set:{model.fitTable=$0;model.selectFitTable($0)})) {
                            ForEach(model.fitTables){Text($0.label).tag($0.id)}
                        }
                    }
                    if !model.fitColumns.isEmpty {
                        Group {
                        Text("\(model.fitRowCount) 行 · 单位：\(model.fitUnit)").font(.caption).foregroundColor(.secondary)
                        DisclosureGroup("查看前3行数据") {ScrollView(.horizontal){Text(model.fitPreview).font(.system(.caption,design:.monospaced)).textSelection(.enabled)}}
                        Divider();Text("2  变量与观测范围").font(.headline)
                        Picker("分析类型",selection:Binding(get:{model.fitKind},set:{kind in model.fitKind=kind;model.fitModels=kind=="relation" ? ["linear"] : ["zero_truncated_poisson"];if kind=="relation" && model.fitY.isEmpty {model.fitY=model.fitColumns.first(where:{$0 != model.fitX}) ?? ""}})) {
                            Text("变量关系 / 规律曲线").tag("relation");Text("离散分布").tag("distribution")
                        }
                        columnPicker(model.fitKind=="relation" ? "X变量" : "观测值",selection:$model.fitX)
                        if model.fitKind=="relation" {columnPicker("Y变量",selection:$model.fitY)}
                        columnPicker(model.fitKind=="relation" ? "最小二乘权重" : "频数列",selection:$model.fitWeight,optional:model.fitKind=="relation" ? "每行等权" : "每行一个观测值")
                        }
                        Group {
                        columnPicker("分别拟合",selection:$model.fitGroup,optional:"全部行合并")
                        Text("按文档、语料组或其他标识分别拟合。每行的层级应与研究问题一致。").font(.caption).foregroundColor(.secondary)
                        Toggle(model.fitKind=="relation" ? "仅纳入X、Y均大于0的行" : "仅纳入大于0的观测值",isOn:$model.fitPositiveOnly).font(.caption)
                        DisclosureGroup("筛选数值范围（留空为不限）") {
                            HStack {Text("X");TextField("下限",text:$model.fitMinX);TextField("上限",text:$model.fitMaxX)}
                            if model.fitKind=="relation" {HStack {Text("Y");TextField("下限",text:$model.fitMinY);TextField("上限",text:$model.fitMaxY)}}
                        }
                        if model.fitKind=="distribution" {Toggle("这是词频谱（频次—词型数，供LNRE使用）",isOn:$model.fitSpectrum).font(.caption)}
                        }
                        Group {
                        Divider();Text("3  候选模型").font(.headline)
                        LazyVGrid(columns:[GridItem(.flexible(),alignment:.leading),GridItem(.flexible(),alignment:.leading)],alignment:.leading,spacing:10) {
                            ForEach(modelNames.filter{$0.2==model.fitKind},id:\.0) {item in
                                Toggle(item.1,isOn:Binding(get:{model.fitModels.contains(item.0)},set:{if $0 {model.fitModels.insert(item.0)} else {model.fitModels.remove(item.0)}})).font(.callout)
                            }
                        }
                        if needsSciPy {HStack {Text("部分模型需要可选的SciPy计算工具。").font(.caption);Button("准备工具"){showResources()}}}
                        if model.fitModels.contains(where:{$0.hasPrefix("lnre_")}) {Text("LNRE使用独立R/zipfR资源；输入须为词频谱。").font(.caption).foregroundColor(.secondary)}
                        }
                    }
                }.frame(maxWidth:.infinity,alignment:.leading).padding(.trailing,6)
            }.frame(width:445).disabled(model.busy)
            Divider()
            VStack(alignment:.leading,spacing:16) {
                Text("4  拟合与比较").font(.headline)
                Text("每个候选模型使用同一组筛选后的观测。缺失、排除、失败原因与模型配置分别保存。").font(.callout).foregroundColor(.secondary)
                HStack {Button("选择输出位置"){model.chooseFitOutput()};Text(model.fitOutput.isEmpty ? "载入数据后自动创建独立目录" : URL(fileURLWithPath:model.fitOutput).lastPathComponent).font(.caption).lineLimit(1)}.disabled(model.busy)
                ProgressView(value:model.progress)
                HStack {
                    Button(model.busy ? "正在运行…" : "开始拟合"){model.startFit()}.buttonStyle(.borderedProminent).disabled(model.busy || model.fitColumns.isEmpty || model.fitModels.isEmpty || model.fitX.isEmpty || (model.fitKind=="relation" && model.fitY.isEmpty))
                    if model.busy {Button("取消并保留结果"){model.stop()}}
                }
                if !model.fitCompletedOutput.isEmpty {
                    HStack {Button("查看图形与报告"){showReport=true};Button("打开结果目录"){model.reveal(model.fitCompletedOutput)}}
                }
                if !model.error.isEmpty {Text(model.error).foregroundColor(.red).textSelection(.enabled)}
                ScrollView {Text(model.fitSummary.isEmpty ? (model.busy ? model.log.suffix(12).joined(separator:"\n") : "选择数据与模型，然后开始拟合。") : model.fitSummary).font(.system(.callout,design:.monospaced)).frame(maxWidth:.infinity,alignment:.leading).textSelection(.enabled)}.frame(maxWidth:.infinity,maxHeight:.infinity).padding(12).background(Color(NSColor.textBackgroundColor)).cornerRadius(8)
                Text("拟合参数和相关关系不自动证明语言规律或因果关系。累计增长点、同文档中的词句可能相互依赖；当前不自动处理这些抽样依赖。").font(.caption).foregroundColor(.secondary)
            }.frame(maxWidth:.infinity,maxHeight:.infinity,alignment:.topLeading)
        }.padding(24)
        .onChange(of:model.fitSettingsID) {_ in model.invalidateFitResult()}
        .sheet(isPresented:$showReport) {
            VStack(spacing:0) {
                HStack {Text("拟合图形与报告").font(.headline);Spacer();Button("关闭"){showReport=false}.keyboardShortcut(.cancelAction)}.padding(16)
                Divider()
                ReportPreview(path:model.fitCompletedOutput+"/report.html")
            }.frame(width:920,height:620)
        }
    }
}
