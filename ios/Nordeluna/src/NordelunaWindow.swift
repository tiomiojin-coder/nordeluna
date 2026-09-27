import SwiftUI
import UIKit

private final class NordelunaRootController: UIViewController {
    private let host = UIHostingController(rootView: NordelunaRootView())

    override func loadView() {
        let root = UIView()
        root.backgroundColor = .black
        view = root
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        addChild(host)
        host.view.backgroundColor = .clear
        host.view.isOpaque = false
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(host.view)
        host.didMove(toParent: self)
    }

    override var supportedInterfaceOrientations: UIInterfaceOrientationMask {
        .allButUpsideDown
    }

    override var prefersStatusBarHidden: Bool {
        NordelunaEngine.shared.phase == .playing && view.bounds.width > view.bounds.height
    }
}

final class NordelunaWindow: UIWindow {
    private static var appWindow: NordelunaWindow?

    static var hostView: UIView? {
        appWindow?.rootViewController?.view
    }

    static func install(in scene: UIWindowScene) {
        guard appWindow == nil else { return }
        let window = NordelunaWindow(windowScene: scene)
        window.backgroundColor = .black
        window.windowLevel = .normal + 1
        window.rootViewController = NordelunaRootController()
        window.makeKeyAndVisible()
        appWindow = window
    }

    static func pushSafeAreaInsets() {
        guard EmpoCoreIsOpen() != 0, let insets = appWindow?.safeAreaInsets else { return }
        gamecore_setSafeAreaInsets(
            Float(insets.top), Float(insets.bottom), Float(insets.left), Float(insets.right))
    }

    override func safeAreaInsetsDidChange() {
        super.safeAreaInsetsDidChange()
        Self.pushSafeAreaInsets()
    }
}
