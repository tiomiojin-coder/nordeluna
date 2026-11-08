module NordelunaOnline
  module NoticeBanner
    LABELS={'info'=>'AVISO','event'=>'EVENTO','maintenance'=>'MANUTENCAO'}
    class << self
      def reset
        ChatPanel.dispose_sprite(@sprite) if @sprite
        @sprite=@current=@last_at=nil;@queue=[];@seen={};@elapsed=0
      end
      def receive(rows)
        unless @server==NordelunaOnline.server
          reset;@server=NordelunaOnline.server
        end
        return unless rows.is_a?(Array) && rows.length<=5
        # Drop expired/withdrawn queued notices whenever the server refreshes.
        active=rows.filter_map { |r| r['id'] if r.is_a?(Hash) }
        @queue.reject! { |r| !active.include?(r['id']) }
        if @current && !active.include?(@current['id'])
          ChatPanel.dispose_sprite(@sprite);@sprite=@current=nil
        end
        rows.each do |row|
          next unless row.is_a?(Hash) && row['id'].is_a?(String) && row['id'].match?(/\A[0-9a-f]{32}\z/) &&
            row['text'].is_a?(String) && row['text'].length.between?(1,180) && !row['text'].match?(/[\x00-\x1f]/) &&
            LABELS.key?(row['kind']) && row['duration'].is_a?(Integer) && row['duration'].between?(6,12) &&
            row['ends'].is_a?(Integer) && row['ends']>Time.now.to_i
          next if @seen[row['id']] || @queue.any? { |r| r['id']==row['id'] } || @current && @current['id']==row['id']
          @queue<<row.dup
        end
        @queue=@queue.last(5)
      end
      def safe?
        $scene.is_a?(Scene_Map) && MapChannel.managed? && MapChannel.safe_map? &&
          !OnlineUI.modal? && !ChatPanel.modal? && !$game_temp.in_menu && !$game_temp.in_battle && !$game_temp.message_window_showing
      end
      def draw
        width=[Graphics.width-32,360].min
        @sprite=ChatPanel.create_sprite(width,66)
        @sprite.z=94_000;@sprite.x=(Graphics.width-width)/2;@sprite.y=50
        bitmap=@sprite.bitmap;pbSetSystemFont(bitmap);bitmap.font.size=14
        lines=ChatPanel.wrap(bitmap,@current['text'],width-24)
        lines=lines.first(2)
        lines[-1]=ChatPanel.fit(bitmap,lines[-1]+'...',width-24) if ChatPanel.wrap(bitmap,@current['text'],width-24).length>2
        height=lines.length==1 ? 47 : 66
        color=@current['kind']=='maintenance' ? Color.new(249,211,117) : Color.new(114,224,231)
        ChatPanel.box(bitmap,0,0,width,height,Color.new(9,20,33,225))
        bitmap.fill_rect(0,0,3,height,color)
        ChatPanel.text(bitmap,LABELS[@current['kind']],12,0,width-24,11,color)
        lines.each_with_index { |line,index| ChatPanel.text(bitmap,line,12,20+index*19,width-24,14) }
      end
      def update
        return unless @server
        at=NordelunaOnline.now
        delta=@last_at ? [[at-@last_at,0].max,0.1].min : 0
        @last_at=at
        unless safe?
          @sprite.visible=false if @sprite
          return
        end
        @queue.reject! { |row| row['ends']<=Time.now.to_i }
        if @current && @current['ends']<=Time.now.to_i
          ChatPanel.dispose_sprite(@sprite);@sprite=@current=nil
        end
        if !@current && !@queue.empty?
          @current=@queue.shift;@elapsed=0
          @seen[@current['id']]=true;@seen.shift while @seen.length>64
          draw
        end
        return unless @current
        @elapsed+=delta
        if @elapsed>=@current['duration']
          ChatPanel.dispose_sprite(@sprite);@sprite=@current=nil
          return
        end
        @sprite.visible=true
        remaining=@current['duration']-@elapsed
        @sprite.opacity=remaining<0.5 ? (remaining*510).to_i : 255
      rescue StandardError => error
        reset
        NordelunaOnline.record_online_error(error,'notice_banner')
      end
    end
  end
  module ReceiveNotices
    def request(url,data)
      reply=super
      NoticeBanner.receive(reply['notices']) if reply.is_a?(Hash) && reply.key?('notices')
      reply
    end
  end
  singleton_class.prepend(ReceiveNotices)
end
EventHandlers.add(:on_frame_update,:nordeluna_notice_banner,proc { NordelunaOnline::NoticeBanner.update })
