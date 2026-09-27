import Foundation

enum TouchControlSlot: String, CaseIterable, Identifiable {
    case a
    case b
    case x
    case y

    var id: String { rawValue }

    var face: String { rawValue.uppercased() }

    var defaultScancode: Int32 {
        switch self {
        case .a: return Int32(GAMECORE_SCANCODE_RETURN)
        case .b: return Int32(GAMECORE_SCANCODE_ESCAPE)
        case .x: return Int32(GAMECORE_SCANCODE_Z)
        case .y: return Int32(GAMECORE_SCANCODE_X)
        }
    }

    var storageKey: String { "nordeluna.controls.\(rawValue).scancode" }
}

struct KeyboardKeyOption: Identifiable, Hashable {
    let label: String
    let scancode: Int32

    var id: Int32 { scancode }
}

let nordelunaKeyboardKeys: [KeyboardKeyOption] = {
    let preferred = [
        KeyboardKeyOption(label: "Enter", scancode: Int32(GAMECORE_SCANCODE_RETURN)),
        KeyboardKeyOption(label: "Z", scancode: Int32(GAMECORE_SCANCODE_Z)),
        KeyboardKeyOption(label: "X", scancode: Int32(GAMECORE_SCANCODE_X)),
        KeyboardKeyOption(label: "C", scancode: Int32(GAMECORE_SCANCODE_C)),
        KeyboardKeyOption(label: "Espaço", scancode: Int32(GAMECORE_SCANCODE_SPACE)),
        KeyboardKeyOption(label: "Escape", scancode: Int32(GAMECORE_SCANCODE_ESCAPE)),
        KeyboardKeyOption(label: "Shift", scancode: Int32(GAMECORE_SCANCODE_LSHIFT)),
        KeyboardKeyOption(label: "Ctrl", scancode: Int32(GAMECORE_SCANCODE_LCTRL)),
        KeyboardKeyOption(label: "Alt", scancode: Int32(GAMECORE_SCANCODE_LALT)),
        KeyboardKeyOption(label: "Tab", scancode: Int32(GAMECORE_SCANCODE_TAB)),
        KeyboardKeyOption(label: "Backspace", scancode: Int32(GAMECORE_SCANCODE_BACKSPACE)),
        KeyboardKeyOption(label: "Seta para cima", scancode: Int32(GAMECORE_SCANCODE_UP)),
        KeyboardKeyOption(label: "Seta para baixo", scancode: Int32(GAMECORE_SCANCODE_DOWN)),
        KeyboardKeyOption(label: "Seta para esquerda", scancode: Int32(GAMECORE_SCANCODE_LEFT)),
        KeyboardKeyOption(label: "Seta para direita", scancode: Int32(GAMECORE_SCANCODE_RIGHT)),
    ]
    let letters = zip(
        Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        Int32(GAMECORE_SCANCODE_A)...Int32(GAMECORE_SCANCODE_Z)
    ).map { KeyboardKeyOption(label: String($0.0), scancode: $0.1) }
    let numbers = zip(
        ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        Int32(GAMECORE_SCANCODE_1)...Int32(GAMECORE_SCANCODE_9)
    ).map { KeyboardKeyOption(label: $0.0, scancode: $0.1) }
        + [KeyboardKeyOption(label: "0", scancode: Int32(GAMECORE_SCANCODE_0))]
    let functions = zip(
        (1...12).map { "F\($0)" },
        Int32(GAMECORE_SCANCODE_F1)...Int32(GAMECORE_SCANCODE_F12)
    ).map { KeyboardKeyOption(label: $0.0, scancode: $0.1) }

    var seen = Set<Int32>()
    return (preferred + letters + numbers + functions).filter {
        seen.insert($0.scancode).inserted
    }
}()

func keyboardKeyName(for scancode: Int32) -> String {
    nordelunaKeyboardKeys.first(where: { $0.scancode == scancode })?.label ?? "Tecla \(scancode)"
}
