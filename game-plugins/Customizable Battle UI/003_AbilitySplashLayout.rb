# The compact themes have only 32px for text. The engine's second row (y=38)
# was outside that bitmap, hiding the ability name after Skill Swap and similar.
module NordelunaAbilitySplashLayout
  def refresh
    return if !bitmap || bitmap.disposed?
    bitmap.clear
    @nordeluna_ability_signature = ability_splash_signature
    return unless @battler
    ability = @battler.abilityName.to_s
    ability = _INTL("Sem habilidade") if ability.empty?
    margin = bitmap.width < 180 ? 4 : 10
    row_height = bitmap.height / 2
    width = bitmap.width - margin * 2
    return if row_height < 1 || width < 1
    font = bitmap.font
    previous = [font.size, font.bold, font.color]
    begin
      font.bold = false
      draw_ability_splash_row(@battler.name.to_s, margin, 0, width, row_height, false)
      draw_ability_splash_row(ability, margin, row_height, width, row_height, true)
    ensure
      font.size, font.bold, font.color = previous
    end
  end

  def update
    return if disposed?
    super
    refresh if visible && @nordeluna_ability_signature != ability_splash_signature
  end

  private

  def ability_splash_signature
    return nil unless @battler
    [@battler.object_id, @battler.name.to_s, @battler.abilityName.to_s]
  end

  def draw_ability_splash_row(label, x, y, width, height, ability)
    bitmap.font.size = [[height, ability ? 22 : 20].min, 10].max
    while bitmap.text_size(label).width > width && bitmap.font.size > 10
      bitmap.font.size -= 1
    end
    if bitmap.text_size(label).width > width
      suffix = "..."
      suffix = suffix[0...-1] while !suffix.empty? && bitmap.text_size(suffix).width > width
      label = label[0...-1] while !label.empty? && bitmap.text_size(label + suffix).width > width
      label += suffix
    end
    align = @side == 0 ? 0 : 2
    bitmap.font.color = self.class::TEXT_SHADOW_COLOR
    bitmap.draw_text(x + 1, y + 1, width - 1, height - 1, label, align) if width > 1 && height > 1
    bitmap.font.color = self.class::TEXT_BASE_COLOR
    bitmap.draw_text(x, y, width, height, label, align)
  end
end

Battle::Scene::AbilitySplashBar.prepend(NordelunaAbilitySplashLayout)
