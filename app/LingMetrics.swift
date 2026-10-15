import SwiftUI
import AppKit
import Foundation
import UniformTypeIdentifiers

struct Metric: Identifiable {
    let id, name, english, category, definition, caution, state, note, sources, scope, method: String
    let selectedByDefault: Bool
    let requirements: [String]
    let details: String
    init(_ d: [String: Any]) {
        id=d["id"] as? String ?? ""; name=d["name"] as? String ?? ""; english=d["english"] as? String ?? ""
        category=d["category"] as? String ?? ""; definition=d["definition"] as? String ?? ""
        caution=d["caution"] as? String ?? "";state=d["state"] as? String ?? "";note=d["note"] as? String ?? ""
        sources=d["sources"] as? String ?? "";scope=d["scope"] as? String ?? "";method=d["method_id"] as? String ?? ""
        selectedByDefault=d["default"] as? Bool ?? false;requirements=d["required_resources"] as? [String] ?? []
        let specs=d["specifications"] as? [[String:Any]] ?? []
        details=specs.map { s in ["操作化名称","定义与公式","分母与归一化","聚合方式","预处理与参数","待核细节或变更"].map { "\($0)：\(s[$0] as? String ?? "")" }.joined(separator:"\n") }.joined(separator:"\n\n")
    }
    var statusText: String { state == "ready" ? "可提取" : state == "method_pending" ? "方法待核" : "需要资源" }
}
struct Resource: Identifiable {
    let id, title, kind, size: String; let installed: Bool; let fields: [String]
    init(_ d: [String:Any]) {id=d["id"] as? String ?? "";title=d["title"] as? String ?? "";kind=d["kind"] as? String ?? "";size=d["size"] as? String ?? "";installed=d["installed"] as? Bool ?? false;fields=d["fields"] as? [String] ?? []}
}

final class AppModel: ObservableObject {
    @Published var metrics: [Metric]=[]; @Published var resources: [Resource]=[]
    @Published var selected: Set<String>=[]; @Published var inputs: [String]=[]
    @Published var columns: [String]=[]; @Published var textColumn="text"
    @Published var output=""; @Published var busy=false; @Published var status="正在载入指标库…"
    @Published var progress=0.0; @Published var log: [String]=[]; @Published var error=""
    @Published var completedOutput=""; @Published var history: [String]=[]
    @Published var window=50; @Published var seed=1729; @Published var useLemma=false
    @Published var advancedOptions="{}"; @Published var retryFailed=false
    @Published var semanticBackend="sbert"
    @Published var cacheSize=""
    private var process: Process?; private var operation=""; private var initialized=false
    private let queue=DispatchQueue(label:"LingMetrics.Output")
    let root: URL
    let cache: URL
    init() {
        root=Bundle.main.resourceURL!
        if let override=ProcessInfo.processInfo.environment["LINGMETRICS_CACHE"] {cache=URL(fileURLWithPath:override)}
        else {cache=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("LingMetrics")}
        history=UserDefaults.standard.stringArray(forKey:"runHistory") ?? []
        command(["catalogue"])
    }
    func append(_ message: String) {log.append(message);if log.count>120 {log.removeFirst(log.count-120)}}
    func isReady(_ metric: Metric) -> Bool {
        if metric.state=="method_pending" {return false}
        let needed=metric.requirements.map {$0=="sbert" ? semanticBackend : $0}
        return needed.allSatisfy {id in resources.contains {$0.id==id && $0.installed}}
    }
    func command(_ arguments: [String]) {
        guard !busy else {return}
        busy=true;error="";operation=arguments[0]
        let p=Process();let stdout=Pipe();let stderr=Pipe()
        p.executableURL=root.appendingPathComponent("python/bin/python3.11")
        p.arguments=["-m","lingmetrics"]+arguments;p.currentDirectoryURL=root
        var environment=ProcessInfo.processInfo.environment
        environment["PYTHONPATH"]=["engine","engine/vendor","base-site"].map {root.appendingPathComponent($0).path}.joined(separator:":")
        environment["PYTHONNOUSERSITE"]="1";environment["PYTHONDONTWRITEBYTECODE"]="1"
        environment["LINGMETRICS_ROOT"]=root.path;environment["LINGMETRICS_CACHE"]=cache.path
        environment["SSL_CERT_FILE"]=root.appendingPathComponent("base-site/certifi/cacert.pem").path
        p.environment=environment;p.standardOutput=stdout;p.standardError=stderr
        var pending=Data()
        stdout.fileHandleForReading.readabilityHandler={ handle in
            let data=handle.availableData
            if data.isEmpty {return}
            self.queue.async {
                pending.append(data)
                while let end=pending.firstIndex(of:10) {
                    let line=pending.subdata(in:0..<end);pending.removeSubrange(0...end)
                    if let d=(try? JSONSerialization.jsonObject(with:line)) as? [String:Any] {
                        DispatchQueue.main.async {self.event(d)}
                    }
                }
            }
        }
        stderr.fileHandleForReading.readabilityHandler={ handle in
            let data=handle.availableData
            guard !data.isEmpty else {return}
            let message=String(decoding:data,as:UTF8.self).trimmingCharacters(in:.whitespacesAndNewlines)
            if !message.isEmpty {DispatchQueue.main.async {self.append(message)}}
        }
        p.terminationHandler={ process in
            DispatchQueue.main.async {
                stdout.fileHandleForReading.readabilityHandler=nil;stderr.fileHandleForReading.readabilityHandler=nil
                self.busy=false;self.process=nil
                if process.terminationStatus != 0 && self.error.isEmpty {self.error="运行未完成，请查看运行信息。";self.status="运行出错"}
                if self.operation=="catalogue" {self.command(["resources"])}
                else if self.operation=="install" || self.operation=="import-resource" {self.command(["catalogue"])}
                self.updateCacheSize()
            }
        }
        process=p
        do {try p.run()} catch {busy=false;self.error=error.localizedDescription;status="引擎启动失败"}
    }
    func event(_ d: [String:Any]) {
        let kind=d["event"] as? String ?? ""
        switch kind {
        case "catalogue":
            metrics=(d["features"] as? [[String:Any]] ?? []).map(Metric.init)
            if !initialized {selected=Set(metrics.filter(\.selectedByDefault).map(\.id));initialized=true}
            status="指标库已就绪，共 \(metrics.count) 个条目"
        case "resources":resources=(d["resources"] as? [[String:Any]] ?? []).map(Resource.init)
        case "columns":
            columns=d["columns"] as? [String] ?? []
            textColumn=columns.first(where:{["text","content","文本"].contains($0.lowercased())}) ?? columns.first ?? "text"
        case "started":progress=0;completedOutput="";status="正在提取 \(d["documents"] ?? 0) 篇文本";append(status)
        case "progress":
            status=d["message"] as? String ?? "正在计算…"
            if let done=d["completed"] as? Int,let total=d["total"] as? Int,total>0 {progress=Double(done)/Double(total)}
            append(status)
        case "finished":
            progress=1;completedOutput=d["output"] as? String ?? output
            status=(d["state"] as? String)=="cancelled" ? "已取消，已完成结果保留，可续算" : "提取完成"
            append(status)
            if let counts=d["status_counts"] as? [String:Any] {
                let names=["computed":"已计算","partial":"部分缺失","undefined":"条件不足","resource_required":"缺少资源","input_required":"需要额外输入","method_pending":"方法待核","error":"计算出错","coverage_insufficient":"覆盖不足"]
                append("结果："+counts.keys.sorted().map {"\(names[$0] ?? $0) \(counts[$0] ?? 0)"}.joined(separator:"，"))
            }
            history.removeAll(where:{$0==completedOutput});history.insert(completedOutput,at:0);history=Array(history.prefix(20));UserDefaults.standard.set(history,forKey:"runHistory")
        case "resource_installed":status="资源准备完成";append(status)
        case "error":error=d["message"] as? String ?? "未知错误";status="运行出错";append(error)
        default:break
        }
    }
    func addInputs(folder: Bool=false) {
        let panel=NSOpenPanel();panel.canChooseFiles = !folder;panel.canChooseDirectories=folder;panel.allowsMultipleSelection=true
        if !folder {panel.allowedContentTypes=[.plainText,.commaSeparatedText]}
        panel.directoryURL=root.appendingPathComponent("examples")
        guard panel.runModal() == .OK else {return}
        for url in panel.urls where !inputs.contains(url.path) {inputs.append(url.path)}
        if let csv=inputs.first(where:{$0.lowercased().hasSuffix(".csv")}) {command(["inspect",csv])}
    }
    func loadExample() {
        inputs=[root.appendingPathComponent("examples/english_sample.csv").path]
        textColumn="text";columns=["doc_id","text","pair_id","section_id"]
        output=cache.appendingPathComponent("runs/example-"+UUID().uuidString.prefix(8)).path
        status="示例已载入，可直接开始提取"
    }
    func chooseOutput() {
        let panel=NSOpenPanel();panel.canChooseFiles=false;panel.canChooseDirectories=true;panel.canCreateDirectories=true;panel.prompt="选择输出目录"
        panel.message="选择保存位置；应用会创建独立的结果文件夹。续算请使用运行记录中的原目录。"
        if panel.runModal() == .OK,let url=panel.url {
            let formatter=DateFormatter();formatter.dateFormat="yyyyMMdd-HHmmss"
            output=url.appendingPathComponent("LingMetrics-"+formatter.string(from:Date())).path
        }
    }
    func start() {
        guard !inputs.isEmpty,!output.isEmpty else {error="请先选择输入文件和输出目录。";return}
        do {
            guard var options=(try JSONSerialization.jsonObject(with:Data(advancedOptions.utf8))) as? [String:Any] else {throw NSError(domain:"LingMetrics",code:1,userInfo:[NSLocalizedDescriptionKey:"高级参数必须是JSON对象"])}
            options["window"]=window;options["seed"]=seed;options["token_unit"]=useLemma ? "lemma" : "wordform";options["semantic_backend"]=semanticBackend
            let job:[String:Any]=["inputs":inputs,"output":output,"features":selected.sorted(),"text_column":textColumn,"options":options,"retry_failed":retryFailed]
            let jobs=cache.appendingPathComponent("jobs");try FileManager.default.createDirectory(at:jobs,withIntermediateDirectories:true)
            let path=jobs.appendingPathComponent(UUID().uuidString+".json");try JSONSerialization.data(withJSONObject:job,options:[.prettyPrinted,.sortedKeys]).write(to:path,options:.atomic)
            command(["run",path.path])
        } catch {self.error=error.localizedDescription}
    }
    func stop() {process?.terminate();status="正在保留已完成结果…"}
    func importResource(_ resource: Resource) {
        let panel=NSOpenPanel();panel.allowedContentTypes=resource.kind=="table" ? [.commaSeparatedText,.tabSeparatedText,.plainText] : resource.id=="fasttext" ? [.json,UTType(filenameExtension:"bin") ?? .data] : [.json]
        if panel.runModal() == .OK,let url=panel.url {command(["import-resource",resource.id,url.path])}
    }
    func removeResource(_ resource: Resource) {
        guard !busy else {return}
        if resource.id=="tensor" {
            let users=resources.filter {$0.installed && ["sbert","causal","mlm","stanza","coref"].contains($0.id)}
            if !users.isEmpty {error="共享运行环境仍被这些资源使用："+users.map(\.title).joined(separator:"、");return}
        }
        let alert=NSAlert();alert.messageText="删除\(resource.title)？";alert.informativeText="已有提取结果会保留。共享计算环境不会随单个资源删除。";alert.addButton(withTitle:"删除资源");alert.addButton(withTitle:"取消")
        guard alert.runModal() == .alertFirstButtonReturn else {return}
        do {
            let folder=cache.appendingPathComponent("resources/"+resource.id)
            let manifest=folder.appendingPathComponent("manifest.json")
            if let data=try? Data(contentsOf:manifest),let meta=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],let model=meta["model_id"] as? String {
                let modelFolder=cache.appendingPathComponent("huggingface/hub/models--"+model.replacingOccurrences(of:"/",with:"--"));try? FileManager.default.removeItem(at:modelFolder)
            }
            if resource.id=="coref" {
                try? FileManager.default.removeItem(at:cache.appendingPathComponent("stanza/en/coref"))
                if let data=try? Data(contentsOf:manifest),let meta=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] {
                    for dep in meta["hf_dependencies"] as? [[String:Any]] ?? [] {
                        if let name=dep["model_id"] as? String {try? FileManager.default.removeItem(at:cache.appendingPathComponent("huggingface/hub/models--"+name.replacingOccurrences(of:"/",with:"--")))}
                    }
                }
            }
            if resource.id=="stanza" {try? FileManager.default.removeItem(at:cache.appendingPathComponent("stanza/en/constituency"))}
            try FileManager.default.removeItem(at:folder);command(["catalogue"])
        } catch {self.error=error.localizedDescription}
    }
    func updateCacheSize() {
        let location=cache
        DispatchQueue.global(qos:.utility).async {
            var bytes:Int64=0
            if let enumerator=FileManager.default.enumerator(at:location,includingPropertiesForKeys:[.fileSizeKey,.isRegularFileKey]) {
                for case let url as URL in enumerator {
                    if let attrs=try? url.resourceValues(forKeys:[.fileSizeKey,.isRegularFileKey]),attrs.isRegularFile==true {bytes+=Int64(attrs.fileSize ?? 0)}
                }
            }
            let label=ByteCountFormatter.string(fromByteCount:bytes,countStyle:.file)
            DispatchQueue.main.async {self.cacheSize=label}
        }
    }
    func reveal(_ path: String) {NSWorkspace.shared.open(URL(fileURLWithPath:path))}
}

struct ContentView: View {
    @EnvironmentObject var model: AppModel
    @State private var tab=0;@State private var search="";@State private var category="全部类别";@State private var detail:Metric?
    @State private var showDownload=false;@State private var download:Resource?
    var filtered:[Metric] {model.metrics.filter { (category=="全部类别" || $0.category==category) && (search.isEmpty || ($0.id+" "+$0.name+" "+$0.english).localizedCaseInsensitiveContains(search)) }}
    var body: some View {
        VStack(spacing:0) {
            HStack {
                Image(systemName:"chart.bar.xaxis").font(.system(size:30)).foregroundColor(.accentColor)
                VStack(alignment:.leading,spacing:3) {Text("LingMetrics").font(.title2.bold());Text("英语语言指标 · 本地提取与研究资料导出").font(.caption).foregroundColor(.secondary)}
                Spacer()
                Picker("页面",selection:$tab) {Text("提取").tag(0);Text("指标库").tag(1);Text("资源").tag(2);Text("运行记录").tag(3)}.pickerStyle(.segmented).frame(width:350)
            }.padding(20)
            Divider()
            if tab==0 {extraction} else if tab==1 {metrics} else if tab==2 {resources} else {history}
            Divider()
            HStack {Text(model.status).font(.caption);Spacer();if model.busy {ProgressView().controlSize(.small)};Text("0.1.0 · Apple Silicon").font(.caption).foregroundColor(.secondary)}.padding(12)
        }.frame(minWidth:1000,minHeight:700)
        .alert("资源下载",isPresented:$showDownload,presenting:download) {r in
            Button("下载") {model.command(["install",r.id])};Button("取消",role:.cancel) {}
        } message: {r in Text("\(r.title)：\(r.size)。模型资源可能同时需要共享运行环境；下载后的实际大小显示在资源页。")}
        .sheet(item:$detail) {m in
            VStack(alignment:.leading,spacing:14) {
                HStack {Text("\(m.id) · \(m.name)").font(.title2.bold());Spacer();Button("关闭"){detail=nil}}
                Text(m.english).foregroundColor(.secondary)
                ScrollView {VStack(alignment:.leading,spacing:16) {
                    Text(m.definition);Text("分析层级：\(m.scope=="corpus" ? "语料" : "文档")\n状态：\(m.note)")
                    Text("测量注意：\(m.caution)")
                    if !m.details.isEmpty {Text(m.details).font(.callout)}
                    ForEach(m.sources.split(separator:"\n").map(String.init),id:\.self) {source in if let url=URL(string:source) {Link("查看来源",destination:url)}}
                }.frame(maxWidth:.infinity,alignment:.leading).textSelection(.enabled)}
            }.padding(24).frame(width:750,height:620)
        }
    }
    var extraction:some View {
        HStack(alignment:.top,spacing:24) {
            VStack(alignment:.leading,spacing:10) {
                Group {
                Text("1  导入文本").font(.headline)
                HStack {Button("添加 TXT / CSV"){model.addInputs()};Button("添加文件夹"){model.addInputs(folder:true)};Button("载入示例"){model.loadExample()}}.disabled(model.busy)
                List {ForEach(model.inputs,id:\.self) {p in HStack {VStack(alignment:.leading){Text(URL(fileURLWithPath:p).lastPathComponent);Text(p).font(.caption2).foregroundColor(.secondary).lineLimit(1)};Spacer();Button {model.inputs.removeAll{$0==p}} label:{Image(systemName:"xmark")}.buttonStyle(.borderless).disabled(model.busy)}}}.frame(height:140)
                if !model.columns.isEmpty {Picker("CSV 文本列",selection:$model.textColumn){ForEach(model.columns,id:\.self){Text($0).tag($0)}}}
                Text("CSV 可附 doc_id、group_id、section_id、pair_id；同一配对编号须对应两篇文本。").font(.caption).foregroundColor(.secondary)
                }
                Group {
                Divider();Text("2  选择输出与参数").font(.headline)
                HStack {Button("选择输出目录"){model.chooseOutput()};Text(model.output.isEmpty ? "尚未选择" : URL(fileURLWithPath:model.output).lastPathComponent).lineLimit(1)}.disabled(model.busy)
                Toggle("使用 lemma 计算词汇统计",isOn:$model.useLemma)
                HStack {Text("多样性窗口");TextField("窗口",value:$model.window,formatter:NumberFormatter()).frame(width:60);Text("随机种子");TextField("种子",value:$model.seed,formatter:NumberFormatter()).frame(width:80)}
                Toggle("重试该目录中失败的阶段",isOn:$model.retryFailed)
                Picker("语义相似度后端",selection:$model.semanticBackend) {Text("MPNet 句向量").tag("sbert");Text("fastText 词向量均值").tag("fasttext")}
                DisclosureGroup("高级参数（JSON）") {TextEditor(text:$model.advancedOptions).font(.system(.caption,design:.monospaced)).frame(height:85);Text("参数与方法说明见使用手册。").font(.caption);Button("打开使用手册"){model.reveal(model.root.appendingPathComponent("docs/extractor.md").path)}}
                }
            }.frame(width:410).disabled(model.busy)
            Divider()
            VStack(alignment:.leading,spacing:16) {
                Text("3  提取与导出").font(.headline)
                HStack {Text("已选 \(model.selected.count) 个条目").font(.title3.bold());Spacer();Button("选择指标"){tab=1}}
                let pending=model.metrics.filter {model.selected.contains($0.id) && !model.isReady($0)}
                if pending.isEmpty {Label("已选指标可开始提取",systemImage:"checkmark.circle").foregroundColor(.green)}
                else {VStack(alignment:.leading,spacing:5) {Text("\(pending.count) 个条目需要资源或方法核验").font(.callout.bold());Text("运行会保留缺失与原因，已具备条件的指标继续计算。").font(.caption).foregroundColor(.secondary);Button("准备所需资源"){tab=2}}}
                Text("导出包含文档特征矩阵、词与句、实际使用的中间计数、语料层结果及运行版本。数值缺失与零分别记录。").font(.callout).foregroundColor(.secondary)
                ProgressView(value:model.progress)
                HStack {Button(model.busy ? "正在运行…" : "开始提取"){model.start()}.buttonStyle(.borderedProminent).disabled(model.busy || model.inputs.isEmpty || model.output.isEmpty || model.selected.isEmpty);if model.busy {Button("取消并保留结果"){model.stop()}};if !model.completedOutput.isEmpty {Button("打开结果文件夹"){model.reveal(model.completedOutput)}}}
                if !model.error.isEmpty {Text(model.error).foregroundColor(.red).textSelection(.enabled)}
                ScrollView {Text(model.log.suffix(25).joined(separator:"\n")).font(.system(.caption,design:.monospaced)).frame(maxWidth:.infinity,alignment:.leading).textSelection(.enabled)}.frame(maxHeight:.infinity).padding(10).background(Color(NSColor.textBackgroundColor)).cornerRadius(8)
            }.frame(maxWidth:.infinity,maxHeight:.infinity,alignment:.topLeading)
        }.padding(24)
    }
    var metrics:some View {
        VStack(spacing:12) {
            HStack {TextField("搜索名称、缩写或编号",text:$search);Picker("类别",selection:$category){Text("全部类别").tag("全部类别");ForEach(Array(Set(model.metrics.map(\.category))).sorted(),id:\.self){Text($0).tag($0)}}.frame(width:250)}
            HStack {Button("常用组合"){model.selected=Set(model.metrics.filter(\.selectedByDefault).map(\.id))};Button("全部可提取"){model.selected=Set(model.metrics.filter{model.isReady($0)}.map(\.id))};Button("选择全库"){model.selected=Set(model.metrics.map(\.id))};Button("清空"){model.selected=[]};Spacer();Text("\(model.selected.count) / \(model.metrics.count)")}.disabled(model.busy)
            List(filtered) {m in
                HStack(spacing:14) {
                    Toggle("",isOn:Binding(get:{model.selected.contains(m.id)},set:{v in if v {model.selected.insert(m.id)} else {model.selected.remove(m.id)}})).labelsHidden().disabled(model.busy)
                    Text(m.id).font(.system(.caption,design:.monospaced)).frame(width:62,alignment:.leading)
                    VStack(alignment:.leading,spacing:3){Text(m.name);Text(m.english).font(.caption).foregroundColor(.secondary)}.frame(maxWidth:.infinity,alignment:.leading)
                    Text(m.scope=="corpus" ? "语料层" : "文档层").font(.caption).foregroundColor(.secondary)
                    Text(m.state=="method_pending" ? "方法待核" : model.isReady(m) ? "可提取" : "需要资源").font(.caption).foregroundColor(model.isReady(m) ? .green : .orange).frame(width:75)
                    Button("详情"){detail=m}
                }.padding(.vertical,3)
            }
        }.padding(20)
    }
    var resources:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack {Text("资源管理").font(.headline);Spacer();Text("本地资源占用：\(model.cacheSize)").foregroundColor(.secondary);Button("打开资源文件夹"){model.reveal(model.cache.path)}}
            Text("计算保留在本机。大型模型按需下载；词表按资源模板导入，原始文件、列映射与校验值随运行记录保存。").font(.callout).foregroundColor(.secondary)
            List(model.resources) {r in
                HStack {VStack(alignment:.leading,spacing:4) {Text(r.title);Text(r.id+" · "+r.size).font(.caption).foregroundColor(.secondary);if !r.fields.isEmpty {Text("字段："+r.fields.joined(separator:", ")).font(.caption2).foregroundColor(.secondary)}};Spacer()
                    if r.installed {Label("已准备",systemImage:"checkmark.circle").font(.caption).foregroundColor(.green);if r.kind != "bundled" {Button("删除"){model.removeResource(r)}}}
                    else if r.kind=="download" {Button("下载"){download=r;showDownload=true}}
                    else {Button("导入"){model.importResource(r)}}
                }.padding(.vertical,5)
            }.disabled(model.busy)
            if !model.error.isEmpty {Text(model.error).foregroundColor(.red)}
            HStack {Button("查看资源模板与口径"){model.reveal(model.root.appendingPathComponent("docs/resources.md").path)};Spacer();Text(model.status).font(.caption)}
        }.padding(20)
    }
    var history:some View {
        VStack(alignment:.leading,spacing:16) {Text("运行记录").font(.headline);Text("每个结果目录包含 run.json、字段字典和状态表。选择原目录及相同配置即可续算。").foregroundColor(.secondary)
            List(model.history,id:\.self){path in HStack {Text(path).lineLimit(2);Spacer();Button("打开"){model.reveal(path)};Button("设为续算目录"){model.output=path;tab=0}}}
        }.padding(24)
    }
}

@main struct LingMetricsApp:App {
    @StateObject private var model=AppModel()
    var body:some Scene {WindowGroup {ContentView().environmentObject(model)}.windowStyle(.titleBar)
        .commands {CommandGroup(replacing:.newItem){};CommandGroup(after:.help){Button("LingMetrics 使用手册"){model.reveal(model.root.appendingPathComponent("docs/extractor.md").path)}}}
    }
}
