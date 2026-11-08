class PokemonGlobalMetadata
  attr_accessor :nordeluna_shop_favorites,:nordeluna_show_badges
end
module NordelunaOnline
  module ShopFavorites
    class << self
      def ids
        pool=$PokemonGlobal.nordeluna_shop_favorites
        rows=pool.is_a?(Hash) ? pool[NordelunaOnline.server] : nil
        rows.is_a?(Array) ? rows : []
      end
      def include?(sku); ids.include?(sku); end
      def toggle(sku)
        raise Error,'Produto invalido.' unless sku.is_a?(String) && sku.match?(/\A[a-z0-9_-]{1,64}\z/)
        old=$PokemonGlobal.nordeluna_shop_favorites
        pool=old.is_a?(Hash) ? old.dup : {}
        rows=ids.dup
        rows.include?(sku) ? rows.delete(sku) : rows<<sku
        raise Error,'Limite de favoritos atingido.' if rows.length>100
        pool[NordelunaOnline.server]=rows
        $PokemonGlobal.nordeluna_shop_favorites=pool
        begin
          Gifts.save!
          saved=Marshal.load(File.binread(SaveData::FILE_PATH))[:global_metadata]
          raise Error,'Favorito nao confirmado no save.' unless saved.nordeluna_shop_favorites==pool
        rescue StandardError
          $PokemonGlobal.nordeluna_shop_favorites=old
          raise
        end
        rows.include?(sku)
      end
      def label(item,balance)
        marked=include?(item['id']) ? '[F] ' : ''
        return marked+item['title']+' / Em breve' if item['enabled']==false
        missing=[item['price']-balance,0].max
        "#{marked}#{item['title']} / #{missing>0 ? "faltam #{missing} LC" : "#{item['price']} LC"}"
      end
      def browse
        return LunaEconomy.recover_purchase if LunaEconomy.pending
        LunaEconomy.sync
        only=false
        loop do
          data=LunaEconomy.snapshot
          rows=data['shop'].select { |r| !only || include?(r['id']) }.sort_by { |r| [r['enabled']==false ? 1 : 0,include?(r['id']) ? 0 : 1,r['price']] }
          choices=rows.map { |r| label(r,data['balance']) }+[only ? 'Mostrar todos' : "Ver favoritos (#{ids.length})",'Voltar']
          n=OnlineUI.choose(only ? 'Meus favoritos' : 'Loja lunar',choices,choices.length-1,"Saldo: #{data['balance']} LC / [F] favorito")
          return if n==choices.length-1
          if n==rows.length
            only=!only
          elsif n>=0 && n<rows.length
            if rows[n]['enabled']==false
              ShopPreview.open(rows[n],data['balance'])
            else
              LunaEconomy.buy(rows[n])
            end
          end
        end
      end
    end
  end

  module ShopPreview
    class << self
      def financials(item,balance)
        {price:item['price'],balance:balance,after:balance-item['price'],missing:[item['price']-balance,0].max,
         buyable:item['enabled']!=false && balance>=item['price']}
      end
      def make_icon(reward,viewport)
        return nil unless reward
        if reward['kind']=='item'
          icon=ItemIconSprite.new(0,0,reward['id'].to_sym,viewport)
          width,height=icon.width,icon.height
          icon.ox=width/2;icon.oy=height/2
        elsif reward['kind']=='pokemon'
          icon=PokemonSprite.new(viewport)
          icon.setSpeciesBitmap(reward['species'].to_sym,0,reward['form'],reward['shiny'],false,false,!!reward['egg'])
          width,height=icon.bitmap ? [icon.bitmap.width,icon.bitmap.height] : [0,0]
        else
          return nil
        end
        if width>0 && height>0
          scale=[2.0,104.0/width,104.0/height].min
          icon.zoom_x=icon.zoom_y=scale
        end
        icon.x=82;icon.y=136
        icon
      rescue StandardError
        icon.dispose if icon && !icon.disposed?
        nil
      end
      def open(item,balance)
        previous=$game_temp.in_menu
        scene=$scene
        $game_temp.in_menu=true
        entered=true
        ChatPanel.hide
        left,top,width,height=OnlineUI.bounds(7)
        viewport=Viewport.new(left,top,width,height);viewport.z=97000
        screen=ChatPanel.create_sprite(width,height);screen.x,screen.y=left,top;screen.z=96000
        rewards=item['rewards'] || []
        labels=rewards.empty? ? ['Disponivel em uma atualizacao futura'] : Gifts.reward_labels(rewards)
        index=0;focus=0;signature=nil
        icon=make_icon(rewards[index],viewport)
        loop do
          Graphics.update;Input.update
          return :back if $scene!=scene
          icon.update if icon
          finance=financials(item,balance)
          favorite=ShopFavorites.include?(item['id'])
          state=[index,focus,favorite]
          buttons=[[14,height-52,(width-48)/3,32],[24+(width-48)/3,height-52,(width-48)/3,32],[34+(width-48)*2/3,height-52,(width-48)/3,32]]
          if signature!=state
            bitmap=screen.bitmap;bitmap.clear
            OnlineUI.draw_background(bitmap,width,height)
            bitmap.font.size=19
            ChatPanel.text(bitmap,ChatPanel.fit(bitmap,item['title'],width-28),14,10,width-28,19,OnlineUI.color(:ACCENT))
            OnlineUI.draw_coin(bitmap,width-124,39)
            ChatPanel.text(bitmap,"#{balance} LC",width-88,44,80,14)
            ChatPanel.box(bitmap,20,80,124,112,Color.new(15,33,51))
            if !icon || !icon.bitmap
              ChatPanel.text(bitmap,item['enabled']==false ? 'Em breve' : 'Sem imagem',28,120,108,14,OnlineUI.color(:MUTED))
            end
            ChatPanel.text(bitmap,item['enabled']==false ? 'Preco: em breve' : "Preco: #{finance[:price]} LC",162,81,width-176,16)
            ChatPanel.text(bitmap,"Seu saldo: #{balance} LC",162,111,width-176,15)
            outcome=item['enabled']==false ? 'Ainda nao esta a venda' : finance[:missing]>0 ? "Faltam: #{finance[:missing]} LC" : "Apos compra: #{finance[:after]} LC"
            ChatPanel.text(bitmap,outcome,162,141,width-176,15,Color.new(247,214,131))
            bitmap.font.size=14
            ChatPanel.wrap(bitmap,labels[index],width-36).first(2).each_with_index { |line,i| ChatPanel.text(bitmap,line,18,204+i*22,width-36,14) }
            names=[finance[:buyable] ? 'Comprar' : item['enabled']==false ? 'Em breve' : 'Sem saldo',favorite ? 'Desfavoritar' : 'Favoritar','Voltar']
            buttons.each_with_index { |rect,i| ChatPanel.button(bitmap,names[i],rect) }
            rect=buttons[focus];bitmap.fill_rect(rect[0]+4,rect[1]+29,rect[2]-8,2,Color.new(245,209,117))
            ChatPanel.text(bitmap,'Esq/dir: opcao / Cima/baixo: premio / Confirmar',14,height-23,width-28,10,OnlineUI.color(:MUTED))
            signature=state
          end
          point=ChatPanel.mouse_click
          point=[point[0]-left,point[1]-top] if point
          action=buttons.index { |rect| ChatPanel.inside?(point,rect) }
          return :back if Input.trigger?(Input::BACK) || action==2
          if Input.trigger?(Input::LEFT)
            focus=(focus-1)%3
          elsif Input.trigger?(Input::RIGHT)
            focus=(focus+1)%3
          elsif Input.trigger?(Input::UP) || Input.trigger?(Input::DOWN)
            index=(index+(Input.trigger?(Input::UP) ? -1 : 1))%labels.length
            icon.dispose if icon && !icon.disposed?
            icon=make_icon(rewards[index],viewport)
          elsif Input.trigger?(Input::USE) || action
            selected=action || focus
            return :buy if selected==0 && finance[:buyable]
            return :back if selected==2
            ShopFavorites.toggle(item['id']) if selected==1
          end
        end
      ensure
        if entered
          icon.dispose if icon && !icon.disposed?
          ChatPanel.dispose_sprite(screen)
          viewport.dispose if viewport && !viewport.disposed?
          $game_temp.in_menu=previous if $game_temp
          Input.update
        end
      end
    end
  end

  module CosmeticBadges
    IDS=%w[lunar_participant community_50].freeze
    class << self
      def show?; $PokemonGlobal && $PokemonGlobal.nordeluna_show_badges!=false; end
      def receive(value)
        raise Error,'Emblema remoto invalido.' unless value=='' || IDS.include?(value)
        @own=value;@server=NordelunaOnline.server
      end
      def own; @server==NordelunaOnline.server ? @own : ''; end
      def reset; @own=@server=nil; end
      def toggle_visibility
        old=$PokemonGlobal.nordeluna_show_badges
        $PokemonGlobal.nordeluna_show_badges=!show?
        begin
          Gifts.save!
        rescue StandardError
          $PokemonGlobal.nordeluna_show_badges=old
          raise
        end
      end
      def menu
        health=NordelunaOnline.test_connection(false)
        raise VersionMismatch,'Emblemas precisam do servidor revisao 10.' unless health['revision'].to_i>=10
        LunaEconomy.sync
        loop do
          data=LunaEconomy.snapshot;rows=data['badges'] || []
          options=rows.map { |r| "#{r['id']==data['equipped_badge'] ? '[Equipado] ' : ''}#{r['title']}" }+['Nenhum emblema no meu nick',show? ? 'Ocultar emblemas nesta tela' : 'Mostrar emblemas nesta tela','Voltar']
          n=OnlineUI.choose('Emblemas cosmeticos',options,options.length-1,'Conquistas de eventos / sem bonus de batalha')
          return if n==options.length-1
          if n==rows.length+1
            toggle_visibility
          else
            selected=n==rows.length ? '' : rows[n]['id']
            reply=LunaEconomy.api('economy_badges','badge'=>selected)
            LunaEconomy.instance_variable_set(:@snapshot,reply)
            receive(reply['equipped_badge'])
          end
        end
      end
    end
  end
end
