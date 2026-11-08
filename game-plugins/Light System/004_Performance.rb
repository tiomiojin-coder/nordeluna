# Installed after the light plugin's alias-based wrapper. This order prevents
# that wrapper from aliasing the performance guard back into itself.
module NordelunaProjectedShadowQuality
  def update
    mode=defined?(NordelunaPerformance) ? NordelunaPerformance.level(:shadows) : 2
    if mode==0 || (mode==1 && !@character.is_a?(Game_Player))
      self.visible=false
      self.opacity=0
      return
    end
    super
  end
end
Sprite_Shadow.prepend(NordelunaProjectedShadowQuality)
