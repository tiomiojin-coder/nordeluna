# The native settings request is asynchronous. Keep pumping the engine window
# until the player closes settings and returns; do not load a map or a save.
if NordelunaOnline::LauncherExperience.config['settings_only']==true && defined?(System) && System.respond_to?(:show_settings)
  hint=Sprite.new
  begin
    hint.bitmap=Bitmap.new(Graphics.width,Graphics.height)
    hint.bitmap.fill_rect(0,0,Graphics.width,Graphics.height,Color.new(12,20,35))
    hint.bitmap.font.size=22
    hint.bitmap.font.color=Color.new(112,224,231)
    hint.bitmap.draw_text(16,72,Graphics.width-32,44,'Teclado e controle',1)
    hint.bitmap.font.size=16
    hint.bitmap.font.color=Color.new(231,240,251)
    hint.bitmap.draw_text(16,140,Graphics.width-32,32,'Configure os botoes na janela de configuracoes.',1)
    hint.bitmap.draw_text(16,180,Graphics.width-32,32,'Depois feche a janela e use Voltar para retornar.',1)
    System.show_settings
    loop do
      Graphics.update
      Input.update
      break if Input.trigger?(Input::BACK)
    end
  ensure
    hint.bitmap.dispose if hint.bitmap && !hint.bitmap.disposed?
    hint.dispose unless hint.disposed?
  end
  exit
end
