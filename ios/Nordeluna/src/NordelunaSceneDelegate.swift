import UIKit

@objc(NordelunaSceneDelegate)
final class NordelunaSceneDelegate: UIResponder, UIWindowSceneDelegate {
    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = scene as? UIWindowScene else { return }
        NordelunaWindow.install(in: windowScene)
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        NordelunaEngine.shared.pauseForBackground()
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        NordelunaEngine.shared.resumeFromBackground()
    }
}
