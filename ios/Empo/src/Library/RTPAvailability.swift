import Foundation

/// Whether Empo has Run-Time Package assets available to the engine.
///
/// mkxp-z can search RTP paths via `mkxp.json`'s `RTP` array, but Empo
/// does not yet expose RTP installation or path configuration. Until that
/// ships, `isConfigured` stays `false` and games that declare RTP in
/// `Game.ini` get a launch warning the user can dismiss.
enum RTPAvailability {
    static var isConfigured: Bool { false }
}
