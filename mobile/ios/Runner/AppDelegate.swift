import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)
    if #available(iOS 10.0, *) {
      UNUserNotificationCenter.current().delegate = self as UNUserNotificationCenterDelegate
    }
    application.registerForRemoteNotifications()
    let launched = super.application(
      application,
      didFinishLaunchingWithOptions: launchOptions
    )
    if let messenger = registrar(forPlugin: "TakeleyShare")?.messenger() {
      FlutterMethodChannel(name: "takeley/share", binaryMessenger: messenger)
        .setMethodCallHandler { call, result in
          Self.handleShare(call: call, result: result)
        }
    }
    return launched
  }

  private static func handleShare(call: FlutterMethodCall, result: @escaping FlutterResult) {
    guard call.method == "share" else {
      result(FlutterMethodNotImplemented)
      return
    }
    guard
      let args = call.arguments as? [String: Any],
      let text = args["text"] as? String, !text.isEmpty,
      let urlString = args["url"] as? String,
      let url = URL(string: urlString)
    else {
      result(
        FlutterError(code: "error", message: "text and url required", details: nil)
      )
      return
    }
    guard let presenter = topViewController() else {
      result(FlutterError(code: "error", message: "No view controller", details: nil))
      return
    }
    let sheet = UIActivityViewController(
      activityItems: [text, url],
      applicationActivities: nil
    )
    if let pop = sheet.popoverPresentationController {
      pop.sourceView = presenter.view
      pop.sourceRect = CGRect(
        x: presenter.view.bounds.midX,
        y: presenter.view.bounds.midY,
        width: 1,
        height: 1
      )
    }
    sheet.completionWithItemsHandler = { _, completed, _, error in
      if let error {
        result(FlutterError(code: "error", message: error.localizedDescription, details: nil))
        return
      }
      result(completed ? "success" : "dismissed")
    }
    presenter.present(sheet, animated: true)
  }

  private static func topViewController() -> UIViewController? {
    let root = UIApplication.shared.connectedScenes
      .compactMap { $0 as? UIWindowScene }
      .flatMap { $0.windows }
      .first { $0.isKeyWindow }?
      .rootViewController
    var top = root
    while let presented = top?.presentedViewController {
      top = presented
    }
    return top
  }
}
