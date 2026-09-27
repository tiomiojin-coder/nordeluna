import UIKit

@MainActor
enum GameViewEmbedder {
    private static weak var embeddedView: UIView?
    private static weak var sourceWindow: UIWindow?

    static func embedWithRetry() {
        if embedIfPossible() { return }
        Task { @MainActor in
            for _ in 0..<60 {
                try? await Task.sleep(for: .milliseconds(50))
                if embedIfPossible() { return }
            }
            NordelunaEngine.shared.reportHostError(
                "O motor iniciou, mas a imagem do jogo não pôde ser anexada à janela do aplicativo.")
        }
    }

    private static func embedIfPossible() -> Bool {
        guard embeddedView == nil else { return true }
        guard let pointer = gamecore_getSDLUIKitWindow() else { return false }
        let window = Unmanaged<UIWindow>.fromOpaque(pointer).takeUnretainedValue()
        guard let gameView = window.rootViewController?.view,
              let hostView = NordelunaWindow.hostView
        else { return false }

        gameView.removeFromSuperview()
        gameView.frame = hostView.bounds
        gameView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        hostView.insertSubview(gameView, at: 0)
        window.isHidden = true
        embeddedView = gameView
        sourceWindow = window
        return true
    }
}
