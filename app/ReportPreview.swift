import SwiftUI
import WebKit

/// Read the generated offline report inside the app, independent of HTML file associations.
struct ReportPreview:NSViewRepresentable {
    let path:String
    func makeNSView(context:Context)->WKWebView {
        let configuration=WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript=false
        return WKWebView(frame:.zero,configuration:configuration)
    }
    func updateNSView(_ view:WKWebView,context:Context) {
        let url=URL(fileURLWithPath:path)
        if view.url != url {view.loadFileURL(url,allowingReadAccessTo:url.deletingLastPathComponent())}
    }
}
