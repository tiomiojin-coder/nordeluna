# Contrast metadata belongs to the pixels currently on the bitmap.
module NordelunaSurfaceLifecycle
  def clear
    result = super
    @journal_regions = nil
    @journal_sequence = nil
    result
  end
end

Bitmap.prepend(NordelunaSurfaceLifecycle)
