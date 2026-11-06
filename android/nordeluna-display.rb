# Android owns the presentation surface. Essentials' desktop resize routine
# switches out of fullscreen and sets Graphics.scale, which shrinks SDL's
# logical window while the Android drawable stays full-sized. The result is
# a small viewport anchored at the bottom-left of the phone's surface.
# Prepend before Scripts.rxdata is evaluated so later definitions of the
# desktop routine cannot override the Android policy (including game resets).
module NordelunaAndroidDisplay
  private

  def pbSetResizeFactor(_factor)
    unless $ResizeInitialized
      Graphics.resize_screen(Settings::SCREEN_WIDTH, Settings::SCREEN_HEIGHT)
      $ResizeInitialized = true
    end
    Graphics.fullscreen = true unless Graphics.fullscreen
    # Size/aspect/original-scale are configured by the Android settings panel.
    # Do not change Graphics.scale or reposition the OS window here.
  end
end

Object.prepend(NordelunaAndroidDisplay) unless Object.ancestors.include?(NordelunaAndroidDisplay)

# Essentials stores event diagnostics outside Exception#message. The native
# mkxp-z dialog calls #message, which otherwise returns only "EventScriptError".
# Define the same class early: Essentials reopens it when its scripts load.
module NordelunaAndroidEventErrorMessage
  def message
    details = instance_variable_get(:@event_message)
    return super unless details.is_a?(String) && !details.empty?
    unless @nordeluna_details_logged
      @nordeluna_details_logged = true
      begin
        directory = Dir.pwd
        File.open(File.join(directory, "nordeluna-event-errors.log"), "ab") do |log|
          log.write("\n[#{Time.now}]\n#{details}\n")
        end
      rescue StandardError
        # Logging must never replace or suppress the original exception.
      end
    end
    details
  end
end

class EventScriptError < Exception
  prepend NordelunaAndroidEventErrorMessage unless ancestors.include?(NordelunaAndroidEventErrorMessage)
end
