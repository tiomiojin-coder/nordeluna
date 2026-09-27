import Foundation

enum BundledGameInstaller {
    struct Installation: Sendable {
        let gameDirectory: URL
        let stateDirectory: URL
        let saveDirectory: URL
    }

    enum InstallError: LocalizedError {
        case bundleMissing
        case invalidBundle

        var errorDescription: String? {
            switch self {
            case .bundleMissing:
                return "Os arquivos do Nordeluna não foram incluídos neste IPA."
            case .invalidBundle:
                return "O pacote do jogo não contém Game.ini ou Data/Scripts.rxdata."
            }
        }
    }

    static func installIfNeeded() throws -> Installation {
        let fm = FileManager.default
        let support = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Nordeluna", isDirectory: true)
        let game = support.appendingPathComponent("Game", isDirectory: true)
        let state = support.appendingPathComponent("State", isDirectory: true)
        let documents = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let saves = documents
            .appendingPathComponent("Nordeluna", isDirectory: true)
            .appendingPathComponent("Saves", isDirectory: true)

        try fm.createDirectory(at: support, withIntermediateDirectories: true)
        try fm.createDirectory(at: state, withIntermediateDirectories: true)
        try fm.createDirectory(at: saves, withIntermediateDirectories: true)

        let ini = game.appendingPathComponent("Game.ini")
        let scripts = game.appendingPathComponent("Data/Scripts.rxdata")
        if fm.fileExists(atPath: ini.path), fm.fileExists(atPath: scripts.path) {
            excludeFromBackup(game)
            return Installation(gameDirectory: game, stateDirectory: state, saveDirectory: saves)
        }

        guard let bundled = Bundle.main.resourceURL?
            .appendingPathComponent("BundledGame", isDirectory: true),
            fm.fileExists(atPath: bundled.path)
        else { throw InstallError.bundleMissing }

        guard fm.fileExists(atPath: bundled.appendingPathComponent("Game.ini").path),
              fm.fileExists(atPath: bundled.appendingPathComponent("Data/Scripts.rxdata").path)
        else { throw InstallError.invalidBundle }

        let staging = support.appendingPathComponent(".Game-installing", isDirectory: true)
        if fm.fileExists(atPath: staging.path) {
            try fm.removeItem(at: staging)
        }
        try fm.copyItem(at: bundled, to: staging)
        if fm.fileExists(atPath: game.path) {
            try fm.removeItem(at: game)
        }
        try fm.moveItem(at: staging, to: game)
        excludeFromBackup(game)
        return Installation(gameDirectory: game, stateDirectory: state, saveDirectory: saves)
    }

    private static func excludeFromBackup(_ directory: URL) {
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var mutable = directory
        try? mutable.setResourceValues(values)
    }
}
