import Combine
import Foundation

@MainActor
final class NordelunaEngine: ObservableObject {
    enum Phase: Equatable {
        case preparing
        case loading
        case playing
        case paused
        case ended
        case failed
    }

    static let shared = NordelunaEngine()

    @Published private(set) var phase: Phase = .preparing
    @Published private(set) var statusText = "Preparando o Nordeluna…"
    @Published var alertMessage: String?
    @Published var controlsVisible = true

    private var started = false
    private var pausedByBackground = false
    private var keyPressStartedAt: [Int32: ContinuousClock.Instant] = [:]
    private var pendingKeyReleases: [Int32: Task<Void, Never>] = [:]
    private static let minimumKeyHold: Duration = .milliseconds(50)

    private init() {}

    func start() {
        guard !started else { return }
        started = true
        phase = .preparing
        statusText = "Copiando os arquivos do jogo na primeira execução…"

        Task {
            do {
                let installation = try await Task.detached(priority: .userInitiated) {
                    try BundledGameInstaller.installIfNeeded()
                }.value
                launch(installation)
            } catch {
                phase = .failed
                statusText = "Não foi possível preparar o jogo."
                alertMessage = error.localizedDescription
            }
        }
    }

    private func launch(_ installation: BundledGameInstaller.Installation) {
        guard let framework = Bundle.main.privateFrameworksURL?
            .appendingPathComponent("MkxpCore.framework/MkxpCore"),
            FileManager.default.fileExists(atPath: framework.path)
        else {
            reportHostError("MkxpCore.framework não foi incluído no aplicativo.")
            return
        }

        guard EmpoCoreOpen(framework.path, "mkxp_") != 0 else {
            reportHostError("O núcleo do RPG Maker XP não pôde ser carregado.")
            return
        }

        registerCallbacks()
        gamecore_setLauncherIdentity("nordeluna")
        gamecore_setConfigOverlayJSON(
            """
            {"windowTitle":"Pokémon Nordeluna","fixedAspectRatio":true,"pathCache":true,"midiSoundFont":"soundfont.sf2"}
            """)

        "".withCString { managed in
            installation.saveDirectory.path.withCString { savePath in
                installation.gameDirectory.appendingPathComponent("Fonts").path.withCString { fonts in
                    var config = GameCoreSessionConfig()
                    config.managedConfigDir = managed
                    config.userDataDirectory = savePath
                    config.sharedFontsDirectory = fonts
                    config.rubyVersion = GAMECORE_RUBY_31
                    config.syntaxTransformMode = GAMECORE_SYNTAX_TRANSFORM_DISABLED
                    config.verticalAlignment = GAMECORE_VALIGN_CENTER
                    config.postloadEnabled = true
                    config.useInGameKeyboard = true
                    config.joiplayCompat = false
                    config.networkEnabled = false
                    gamecore_applySessionConfig(&config)
                }
            }
        }

        gamecore_resetSessionState()
        gamecore_setGameControllerCaptureEnabled(false)
        gamecore_setTouchMouseEnabled(false)
        NordelunaWindow.pushSafeAreaInsets()

        phase = .loading
        statusText = "Iniciando Pokémon Nordeluna…"
        gamecore_setGamePath(installation.gameDirectory.path)
        RunLoop.main.perform {
            _ = EmpoCoreRunEngine()
        }
    }

    private func registerCallbacks() {
        gamecore_setFrameRenderedCallback({ _ in
            Task { @MainActor in
                GameViewEmbedder.embedWithRetry()
                if NordelunaEngine.shared.phase != .paused {
                    NordelunaEngine.shared.phase = .playing
                    NordelunaEngine.shared.statusText = ""
                }
            }
        }, nil)

        gamecore_setEngineTerminatedCallback({ _ in
            Task { @MainActor in
                let engine = NordelunaEngine.shared
                engine.phase = .ended
                engine.statusText = "O jogo foi encerrado. Feche e abra o aplicativo para jogar novamente."
            }
        }, nil)

        gamecore_setPausedCallback({ _ in
            Task { @MainActor in
                let engine = NordelunaEngine.shared
                if !engine.pausedByBackground { engine.phase = .paused }
            }
        }, nil)

        gamecore_setResumedCallback({ _ in
            Task { @MainActor in
                let engine = NordelunaEngine.shared
                engine.pausedByBackground = false
                engine.phase = .playing
            }
        }, nil)

        gamecore_setErrorMessageCallback({ message, _ in
            guard let message else { return }
            let text = String(cString: message)
            Task { @MainActor in
                NordelunaEngine.shared.alertMessage = text
            }
        }, nil)

        gamecore_setInfoMessageCallback({ message, _ in
            guard let message else { return }
            let text = String(cString: message)
            Task { @MainActor in
                NordelunaEngine.shared.alertMessage = text
            }
        }, nil)
    }

    func dismissAlert() {
        alertMessage = nil
        guard EmpoCoreIsOpen() != 0 else { return }
        gamecore_signalErrorDismissed()
        gamecore_signalInfoDismissed()
    }

    func reportHostError(_ message: String) {
        phase = .failed
        statusText = "Falha ao iniciar o jogo."
        alertMessage = message
    }

    func setKey(_ scancode: Int32, pressed: Bool) {
        guard EmpoCoreIsOpen() != 0 else { return }
        if pressed {
            guard phase == .playing else { return }
            pendingKeyReleases.removeValue(forKey: scancode)?.cancel()
            keyPressStartedAt[scancode] = .now
            gamecore_injectKeyEvent(scancode, 1)
            return
        }

        pendingKeyReleases.removeValue(forKey: scancode)?.cancel()
        guard let started = keyPressStartedAt[scancode] else {
            gamecore_injectKeyEvent(scancode, 0)
            return
        }
        let held = ContinuousClock.now - started
        if held >= Self.minimumKeyHold {
            keyPressStartedAt.removeValue(forKey: scancode)
            gamecore_injectKeyEvent(scancode, 0)
            return
        }
        let remaining = Self.minimumKeyHold - held
        pendingKeyReleases[scancode] = Task { @MainActor in
            try? await Task.sleep(for: remaining)
            guard !Task.isCancelled else { return }
            self.keyPressStartedAt.removeValue(forKey: scancode)
            self.pendingKeyReleases.removeValue(forKey: scancode)
            gamecore_injectKeyEvent(scancode, 0)
        }
    }

    private func releaseAllKeys() {
        for task in pendingKeyReleases.values { task.cancel() }
        pendingKeyReleases.removeAll()
        for scancode in keyPressStartedAt.keys {
            gamecore_injectKeyEvent(scancode, 0)
        }
        keyPressStartedAt.removeAll()
    }

    func pause() {
        guard phase == .playing else { return }
        releaseAllKeys()
        gamecore_requestPause()
    }

    func resume() {
        guard phase == .paused else { return }
        gamecore_requestResume()
    }

    func pauseForBackground() {
        guard EmpoCoreIsOpen() != 0, phase == .playing else { return }
        releaseAllKeys()
        pausedByBackground = true
        gamecore_requestPause()
    }

    func resumeFromBackground() {
        guard EmpoCoreIsOpen() != 0, pausedByBackground, gamecore_isPaused() else { return }
        gamecore_requestResume()
    }
}
