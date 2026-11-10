module NordelunaOnline
  module OnlineUI
    class << self
      def connection_badge
        case MapChannel.instance_variable_get(:@connection_state)
        when :connected then ['Conectado',[100,218,171]]
        when :connecting,:reconnecting then ['Reconectando',[244,190,102]]
        else ['Offline',[156,167,180]]
        end
      end

      # Pixel-drawn icons stay sharp and do not depend on an emoji font.
      def card_icon(bitmap,kind,x,y)
        c=color(:ACCENT)
        case kind
        when :plaza
          bitmap.fill_rect(x+10,y+4,4,24,c);bitmap.fill_rect(x+2,y+24,24,3,c)
          bitmap.fill_rect(x+4,y+7,18,3,c);bitmap.fill_rect(x+8,y+1,8,4,c)
        when :battle
          6.times { |n| bitmap.fill_rect(x+3+n*3,y+3+n*3,4,4,c);bitmap.fill_rect(x+21-n*3,y+3+n*3,4,4,c) }
          bitmap.fill_rect(x+1,y+20,9,3,c);bitmap.fill_rect(x+18,y+20,9,3,c)
        when :friends
          [1,17].each { |dx| bitmap.fill_rect(x+dx+2,y+3,7,8,c);bitmap.fill_rect(x+dx,y+14,12,11,c) }
        when :shop
          bitmap.fill_rect(x+3,y+9,23,17,c);bitmap.fill_rect(x+8,y+2,13,3,c)
          bitmap.fill_rect(x+8,y+3,3,9,c);bitmap.fill_rect(x+18,y+3,3,9,c)
        end
      end

      def home_cards
        previous=$game_temp.in_menu;scene=$scene
        @depth=(@depth || 0)+1;entered=true;$game_temp.in_menu=true;ChatPanel.hide
        left,top,width,height=bounds
        screen=ChatPanel.create_sprite(width,height);screen.x=left;screen.y=top;screen.z=96000+@depth
        gap=8;cw=(width-36)/2;ch=(height-142)/2
        rectangles=4.times.map { |i| [14+(i%2)*(cw+gap),58+(i/2)*(ch+gap),cw,ch] }
        rectangles += 4.times.map { |i| [14+(i%2)*(cw+gap),height-70+(i/2)*30,cw,26] }
        selected=0;signature=nil;touch=nil
        loop do
          Graphics.update;Input.update
          return 11 if $scene!=scene || Input.trigger?(Input::BACK)
          selected=(selected-2)%8 if Input.trigger?(Input::UP)
          selected=(selected+2)%8 if Input.trigger?(Input::DOWN)
          selected^=1 if Input.trigger?(Input::LEFT) || Input.trigger?(Input::RIGHT)
          activated=Input.trigger?(Input::USE)
          point=pointer;local=point && [point[0]-left,point[1]-top]
          touch=local if pointer_start? && local
          if touch && !pointer_down?
            if local && (local[0]-touch[0]).abs<8 && (local[1]-touch[1]).abs<8
              hit=rectangles.index { |r| ChatPanel.inside?(local,r) && ChatPanel.inside?(touch,r) }
              if hit;selected=hit;activated=true;end
            end
            touch=nil
          end
          return [0,6,1,12,5,9,:more,11][selected] if activated && selected!=6
          return SocialHub.more if activated && selected==6
          state=[selected,connection_badge,Friends.badge,MapChannel.members,LunaEconomy.pending,Gifts.pending!=nil]
          next if signature==state
          bitmap=screen.bitmap;bitmap.clear
          ChatPanel.box(bitmap,0,0,width,height,color(:BACKGROUND))
          ChatPanel.text(bitmap,'ONLINE',14,8,160,22,color(:ACCENT))
          ChatPanel.text(bitmap,ChatPanel.fit(bitmap,NordelunaOnline.nickname,width-28),14,32,width-28,13,color(:MUTED))
          labels=['Praca','Batalhas','Amigos','Loja','Chat','Conexao','Mais','Voltar']
          notes=["#{MapChannel.members} na sala",'Procurar ou convidar',Friends.badge>0 ? "#{Friends.badge} avisos" : 'Sua lista de amigos',LunaEconomy.pending ? 'Compra pendente' : 'Itens, ovos e roupas']
          rectangles.each_with_index do |r,i|
            x,y,w,h=r;active=selected==i
            ChatPanel.box(bitmap,x,y,w,h,Color.new(*(active ? [29,65,83] : [18,35,51])))
            bitmap.fill_rect(x,y,3,h,color(:ACCENT)) if active
            if i<4
              card_icon(bitmap,[:plaza,:battle,:friends,:shop][i],x+10,y+10)
              ChatPanel.text(bitmap,labels[i],x+47,y+9,w-55,18,color(:TEXT))
              ChatPanel.text(bitmap,ChatPanel.fit(bitmap,notes[i],w-20),x+10,y+h-29,w-20,12,color(:MUTED))
            else
              label=labels[i];offset=10
              if i==5
                label,rgb=connection_badge
                bitmap.fill_rect(x+10,y+10,6,6,Color.new(*rgb));offset=24
              end
              ChatPanel.text(bitmap,label,x+offset,y,w-offset-6,13,color(:TEXT))
            end
          end
          signature=state
        end
      ensure
        if entered
          ChatPanel.dispose_sprite(screen);$game_temp.in_menu=previous if $game_temp
          @depth=[(@depth || 1)-1,0].max;Input.update
        end
      end
    end
  end
end
