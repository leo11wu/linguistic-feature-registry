import AppKit
import Foundation

let input = FileHandle.standardInput.readDataToEndOfFile()
let object = try JSONSerialization.jsonObject(with: input) as! [String: Any]
let text = object["text"] as? String ?? ""
let checker = NSSpellChecker.shared
var issues: [[String: Any]] = []
let length = (text as NSString).length
let tag = NSSpellChecker.uniqueSpellDocumentTag()
for kind in ["spelling", "grammar"] {
    var position = 0
    while position < length {
        if kind == "spelling" {
            let range = checker.checkSpelling(of: text, startingAt: position, language: "en_US", wrap: false, inSpellDocumentWithTag: tag, wordCount: nil)
            if range.location == NSNotFound || range.length == 0 { break }
            issues.append(["kind": kind, "start": range.location, "length": range.length, "offset_unit": "UTF-16", "text": (text as NSString).substring(with: range)])
            position = NSMaxRange(range)
        } else {
            var details: NSArray? = nil
            let range = checker.checkGrammar(of: text, startingAt: position, language: "en_US", wrap: false, inSpellDocumentWithTag: tag, details: &details)
            if range.location == NSNotFound || range.length == 0 { break }
            for detail in details as? [[String: Any]] ?? [] {
                let relative = (detail[NSGrammarRange] as? NSValue)?.rangeValue ?? NSRange(location: 0, length: range.length)
                issues.append(["kind": kind, "start": range.location + relative.location, "length": relative.length, "offset_unit": "UTF-16", "description": detail[NSGrammarUserDescription] as? String ?? "grammar flag"])
            }
            position = NSMaxRange(range)
        }
    }
}
checker.closeSpellDocument(withTag: tag)
let result: [String: Any] = ["issues": issues, "checker": "Apple NSSpellChecker", "language": "en_US", "macos": ProcessInfo.processInfo.operatingSystemVersionString]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]))
