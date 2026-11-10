package com.mkxpz.launcher;

import android.app.*;
import android.os.*;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.provider.Settings;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import com.mkxpz.MainActivity;
import com.mkxpz.BuildConfig;

/** Accessible launch screen: buttons work with touch, D-pad and a controller. */
public final class ClientLauncher extends Activity {
    public static volatile boolean gameRunning=false;
    private static final String PREFS="nordeluna_client_launcher";
    private LinearLayout content;private TextView status,news;private ProgressBar progress;
    private TextView newsVersion;private String fullNews="As novidades aparecem ao consultar uma versão publicada.";
    private Spinner channels;private boolean busy;private File pendingApk;
    private final ArrayList<Button> launchActions=new ArrayList<>();
    private static final int BG=Color.rgb(11,17,29),CARD=Color.rgb(20,31,47),INK=Color.rgb(235,242,250),MUTED=Color.rgb(159,178,198),ACCENT=Color.rgb(100,224,220),GOLD=Color.rgb(232,199,128);
    private final android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
    private android.content.SharedPreferences prefs(){return getSharedPreferences(PREFS,MODE_PRIVATE);}
    private String ownChannel(){return getPackageName().endsWith(".testers")?"testers":"stable";}
    private JSONObject testerRelease;
    private static volatile long testerAllowedUntil;
    private JSONObject testerCredentials()throws Exception{return new JSONObject(prefs().getString("tester_credentials","{}"));}
    private void authorizeTester()throws Exception{
        JSONObject result=TesterAccess.authorize(testerCredentials());testerRelease=result.optJSONObject("release");
        testerAllowedUntil=android.os.SystemClock.elapsedRealtime()+15*60*1000;
    }
    private boolean inviteIfNeeded(){
        if(!channel().equals("testers")||prefs().contains("tester_credentials"))return false;
        activateTester();return true;
    }
    private void activateTester(){
        EditText entry=new EditText(this);entry.setSingleLine(true);entry.setHint("NLT-...");entry.setInputType(129);
        new AlertDialog.Builder(this).setTitle("Convite de tester").setMessage("Cole sua chave individual. Ela libera um aparelho e exige conexão para validar o acesso. Para trocar de aparelho, peça outro convite.").setView(entry)
        .setPositiveButton("Ativar",(d,w)->work(()->{JSONObject credentials=TesterAccess.redeem(entry.getText().toString());prefs().edit().putString("tester_credentials",credentials.toString()).commit();authorizeTester();handler.post(()->status.setText("Acesso ativado. Use Atualizar para baixar a versão de testes."));}))
        .setNeutralButton("Remover acesso local",(d,w)->{prefs().edit().remove("tester_credentials").apply();testerAllowedUntil=0;status.setText("Acesso removido deste aplicativo.");}).setNegativeButton("Voltar",null).show();
    }
    private String channel(){return prefs().getString("channel",ownChannel());}
    private String selectedPackage(){return "com.tiomi.nordeluna"+(channel().equals("testers")?".testers":"");}
    @SuppressWarnings("deprecation") private void trustChannelPackage()throws Exception{
        PackageManager pm=getPackageManager();PackageInfo other=pm.getPackageInfo(selectedPackage(),PackageManager.GET_SIGNATURES),current=pm.getPackageInfo(getPackageName(),PackageManager.GET_SIGNATURES);
        if(other.signatures==null||current.signatures==null||!new HashSet<>(Arrays.asList(other.signatures)).equals(new HashSet<>(Arrays.asList(current.signatures))))throw new IOException("O aplicativo deste canal não tem a assinatura oficial. O convite não foi compartilhado.");
    }
    private File state(){return new File(getFilesDir(),"client-launcher");}
    private File saves(){return new File(getFilesDir(),"player-data/"+channel());}
    private File backups(){return new File(getFilesDir(),"player-backups/"+channel());}
    private interface Work { void run() throws Exception; }
    @Override public void onCreate(Bundle state){
        setTheme(android.R.style.Theme_Material_NoActionBar);
        if(gameRunning){super.onCreate(state);startActivity(new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));finish();return;}
        if(getIntent().getBooleanExtra("open_own_channel",false))prefs().edit().putString("channel",ownChannel()).apply();
        super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        String invited=getIntent().getStringExtra("tester_credentials");
        if(ownChannel().equals("testers")&&invited!=null&&invited.length()<1024)prefs().edit().putString("tester_credentials",invited).commit();
        ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(BG);scroll.setFillViewport(true);scroll.setClipToPadding(false);
        FrameLayout frame=new FrameLayout(this);scroll.addView(frame,new ScrollView.LayoutParams(-1,-2));
        content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(dp(20),dp(24),dp(20),dp(28));
        int width=getResources().getConfiguration().screenWidthDp;FrameLayout.LayoutParams page=new FrameLayout.LayoutParams(width>840?dp(840):-1,-2,Gravity.TOP|Gravity.CENTER_HORIZONTAL);frame.addView(content,page);setContentView(scroll);
        LinearLayout hero=new LinearLayout(this);hero.setGravity(Gravity.CENTER_VERTICAL);hero.setPadding(0,0,0,dp(22));content.addView(hero);
        ImageView logo=new ImageView(this);logo.setImageDrawable(getApplicationInfo().loadIcon(getPackageManager()));logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);hero.addView(logo,new LinearLayout.LayoutParams(dp(64),dp(64)));
        LinearLayout heading=new LinearLayout(this);heading.setOrientation(1);heading.setPadding(dp(16),0,0,0);hero.addView(heading,new LinearLayout.LayoutParams(0,-2,1));
        text(heading,"POKÉMON",11,GOLD,true);text(heading,"NORDELUNA",25,INK,true);text(heading,"Sua próxima aventura começa aqui.",14,MUTED,false);
        LinearLayout start=card();text(start,"CANAL DA AVENTURA",11,MUTED,true);
        channels=new Spinner(this);channels.setContentDescription("Canal do jogo");channels.setBackground(tintBox(Color.rgb(28,44,61),dp(10),Color.rgb(49,71,89)));channels.setPadding(dp(12),0,dp(8),0);channels.setPopupBackgroundDrawable(tintBox(CARD,dp(12),Color.rgb(49,71,89)));channels.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Estável","Testers · saves separados"}));channels.setSelection(channel().equals("testers")?1:0);LinearLayout.LayoutParams channelSize=new LinearLayout.LayoutParams(-1,dp(52));channelSize.setMargins(0,dp(8),0,dp(14));start.addView(channels,channelSize);
        channels.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int position,long id){if(busy)return;prefs().edit().putString("channel",position==1?"testers":"stable").apply();}});
        button(start,"JOGAR","Continuar sua aventura",true,()->play());button(start,"Atualizar","Conferir novidades e downloads",false,()->checkUpdates(true));
        LinearLayout updates=card();text(updates,"Novidades de Nordeluna",20,ACCENT,true);
        ImageView feature=new ImageView(this);feature.setImageDrawable(getApplicationInfo().loadIcon(getPackageManager()));feature.setScaleType(ImageView.ScaleType.FIT_CENTER);feature.setContentDescription("Pokémon Nordeluna");updates.addView(feature,new LinearLayout.LayoutParams(-1,dp(110)));
        newsVersion=text(updates,"VERSÃO "+BuildConfig.VERSION_NAME,13,GOLD,true);news=text(updates,"Confira o que mudou antes de jogar. No canal estável, sua aventura também continua offline.",15,INK,false);news.setPadding(0,dp(12),0,dp(4));news.setTextIsSelectable(true);
        button(updates,"Ler todas as novidades","Histórico desta atualização",false,()->showNews());
        LinearLayout tools=card();text(tools,"DO SEU JEITO",11,MUTED,true);
        boolean columns=width>=600&&getResources().getConfiguration().fontScale<=1.3f;
        LinearLayout row=actionRow(tools);
        button(row,"Configurações","Tela, áudio e controles",false,()->settings());
        if(!columns)row=actionRow(tools);button(row,"Backups","Restaurar progresso",false,()->showBackups());
        row=actionRow(tools);button(row,"Reparar","Conferir arquivos",false,()->repairInstallation());
        if(!columns)row=actionRow(tools);button(row,"Diagnóstico","Conexão e relatórios",false,()->diagnostics());
        button(tools,"Acesso de tester","Ativar ou trocar convite",false,()->activateTester());
        status=label("Versão "+BuildConfig.VERSION_NAME+" • pronto para jogar",13);status.setTextColor(MUTED);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setProgressTintList(ColorStateList.valueOf(ACCENT));progress.setIndeterminateTintList(ColorStateList.valueOf(ACCENT));progress.setVisibility(View.GONE);content.addView(progress,new LinearLayout.LayoutParams(-1,dp(5)));
        CrashDiagnostics.install(this,()->handler.post(()->{if(!isFinishing()&&CrashDiagnostics.hasUnseenReport(this))new AlertDialog.Builder(this).setTitle("O jogo foi interrompido").setMessage("Existe um diagnóstico do fechamento anterior. Você pode exportar um resumo sem saves ou dados de login.").setPositiveButton("Exportar",(d,w)->exportReport()).setNegativeButton("Depois",null).show();}));
        checkUpdates(getIntent().getBooleanExtra("check_update",false));
    }
    private int dp(float value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private GradientDrawable tintBox(int color,float radius,int border){GradientDrawable box=new GradientDrawable();box.setColor(color);box.setCornerRadius(radius);box.setStroke(dp(1),border);return box;}
    private TextView text(LinearLayout parent,String value,int size,int color,boolean bold){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));v.setPadding(0,dp(3),0,dp(4));parent.addView(v,new LinearLayout.LayoutParams(-1,-2));return v;}
    private TextView label(String value,int size){return text(content,value,size,INK,false);}
    private LinearLayout card(){LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(dp(18),dp(16),dp(18),dp(16));box.setBackground(tintBox(CARD,dp(18),Color.rgb(43,62,81)));LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);params.bottomMargin=dp(16);content.addView(box,params);return box;}
    private LinearLayout actionRow(LinearLayout parent){LinearLayout row=new LinearLayout(this);row.setOrientation(LinearLayout.HORIZONTAL);parent.addView(row,new LinearLayout.LayoutParams(-1,-2));return row;}
    private void button(LinearLayout parent,String title,String caption,boolean primary,Runnable action){
        Button b=new Button(this);b.setText(title+"\n"+caption);b.setAllCaps(false);b.setTextSize(primary?18:15);b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));b.setTextColor(primary?BG:INK);b.setGravity(Gravity.CENTER_VERTICAL|Gravity.START);b.setPadding(dp(18),dp(12),dp(18),dp(12));b.setMinHeight(dp(76));b.setMinimumWidth(0);b.setStateListAnimator(null);b.setFocusable(true);b.setContentDescription(title+". "+caption);
        GradientDrawable face=tintBox(primary?ACCENT:Color.rgb(27,43,61),dp(12),primary?ACCENT:Color.rgb(49,71,89));
        android.graphics.drawable.StateListDrawable states=new android.graphics.drawable.StateListDrawable();states.addState(new int[]{android.R.attr.state_focused},tintBox(primary?ACCENT:Color.rgb(38,61,78),dp(12),GOLD));states.addState(new int[]{},face);b.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.argb(60,232,199,128)),states,null));
        b.setOnClickListener(v->{if(!busy)action.run();});b.setOnFocusChangeListener((v,focused)->b.setAlpha(b.isEnabled()?1f:.45f));
        LinearLayout.LayoutParams params=parent.getOrientation()==LinearLayout.HORIZONTAL?new LinearLayout.LayoutParams(0,-2,1):new LinearLayout.LayoutParams(-1,-2);params.setMargins(dp(3),dp(7),dp(3),dp(3));parent.addView(b,params);launchActions.add(b);
    }
    private void work(Work task){if(busy)return;busy=true;channels.setEnabled(false);for(Button b:launchActions){b.setEnabled(false);b.setAlpha(.45f);}progress.setVisibility(View.VISIBLE);progress.setIndeterminate(true);new Thread(()->{try{task.run();}catch(Exception error){handler.post(()->status.setText("Não foi possível concluir: "+error.getMessage()));}finally{handler.post(()->{busy=false;channels.setEnabled(true);for(Button b:launchActions){b.setEnabled(true);b.setAlpha(1f);}progress.setVisibility(View.GONE);});}},"Nordeluna launcher").start();}
    private void showProgress(String text,int percent){handler.post(()->{status.setText(text+" • "+percent+"%");progress.setIndeterminate(false);progress.setProgress(percent);});}
    private void play(){if(inviteIfNeeded())return;work(()->{
        if(channel().equals("testers"))authorizeTester();
        if(ownChannel().equals("testers")&&(testerRelease==null||ClientFiles.verifyCatalog(testerRelease.getJSONObject("catalog").toString(),LauncherKeys.MODULUS).getJSONObject("channels").getJSONObject("testers").getJSONObject("android").getInt("code")!=BuildConfig.VERSION_CODE))throw new IOException("Use Atualizar para instalar a versão de testes autorizada.");
        if(!channel().equals(ownChannel())){Intent open=getPackageManager().getLaunchIntentForPackage(selectedPackage());if(open==null)throw new IOException("Use Atualizar para instalar este canal. Seus saves serão separados do aplicativo estável.");trustChannelPackage();open.putExtra("open_own_channel",true);if(channel().equals("testers"))open.putExtra("tester_credentials",testerCredentials().toString());handler.post(()->startActivity(open));return;}
        ClientRepair.recover(gameFolder(this));migrateStable(this,gameFolder(this));saves().mkdirs();ClientFiles.backup(saves(),backups(),channel());
        handler.post(()->{startActivity(new Intent(this,MainActivity.class));});
    });}
    public static File gameFolder(Context c){File base=c.getExternalFilesDir(null);if(base==null)base=c.getFilesDir();return new File(base,"mkxp-z");}
    private static void migrateStable(Context c,File game)throws Exception{
        File dest=new File(c.getFilesDir(),"player-data/stable");dest.mkdirs();if(!ClientFiles.saveFiles(dest).isEmpty())return;
        File[] candidates={new File(game,"Saves"),new File(c.getFilesDir(),"Saves")};
        for(File source:candidates)if(source.isDirectory())for(File file:ClientFiles.saveFiles(source)){File to=ClientFiles.child(dest,source.toURI().relativize(file.toURI()).getPath());if(!to.exists()){to.getParentFile().mkdirs();try(InputStream in=new FileInputStream(file);OutputStream out=new FileOutputStream(to)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}}}
        for(File base:new File[]{game,c.getFilesDir()}){File old=new File(base,"Game.rxdata"),to=new File(dest,"Game.rxdata");if(old.isFile()&&!to.exists()){try(InputStream in=new FileInputStream(old)){ClientFiles.write(to,ClientFiles.bounded(in,64*1024*1024));}}}
    }
    /** Called after bundled extraction, before the native/Ruby thread starts. */
    public static void prepareGame(Context c,File game)throws Exception{
        ClientRepair.recover(game);
        android.content.SharedPreferences p=c.getSharedPreferences(PREFS,MODE_PRIVATE);migrateStable(c,game);String channel=c.getPackageName().endsWith(".testers")?"testers":"stable";
        if(channel.equals("testers")&&android.os.SystemClock.elapsedRealtime()>testerAllowedUntil)throw new IOException("Abra pelo launcher e valide seu convite de tester.");
        File saves=new File(c.getFilesDir(),"player-data/"+channel);saves.mkdirs();JSONObject cfg=new JSONObject();cfg.put("channel",channel);cfg.put("save_root",saves.getAbsolutePath());cfg.put("volume",p.getInt("volume",80));
        if(channel.equals("testers"))cfg.put("tester",new JSONObject(p.getString("tester_credentials","{}")));
        ClientFiles.write(new File(game,".nordeluna-launcher.json"),cfg.toString().getBytes(StandardCharsets.UTF_8));
    }
    public static File selectedSaves(Context c){String ch=c.getPackageName().endsWith(".testers")?"testers":"stable";return new File(c.getFilesDir(),"player-data/"+ch);}
    private void repairInstallation(){
        if(busy||gameRunning)return;
        if(!channel().equals(ownChannel())){status.setText("Abra o outro canal para reparar a instalação dele.");return;}
        if(getSharedPreferences("mkxpz_prefs",0).getInt("bundled_game_version",0)!=BuildConfig.VERSION_CODE){status.setText("Toque em Jogar uma vez para concluir a preparação desta versão do APK.");return;}
        ProgressDialog dialog=new ProgressDialog(this);dialog.setTitle("Reparar instalação");dialog.setMessage("Conferindo arquivos sem alterar seus saves");dialog.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);dialog.setMax(100);dialog.setCancelable(false);dialog.show();
        work(()->{try{
            File game=gameFolder(this);ClientRepair.recover(game);ClientFiles.backup(saves(),backups(),channel());
            int repaired=ClientRepair.repair(game,()->getAssets().open("nordeluna-game.zip"),(text,percent)->{showProgress(text,percent);handler.post(()->{dialog.setMessage(text);dialog.setProgress(percent);});});
            handler.post(()->status.setText(repaired==0?"Instalação íntegra. Nenhum download necessário.":repaired+" arquivo(s) restaurado(s), sem baixar outro APK. Saves preservados."));
        }finally{handler.post(()->dialog.dismiss());}});
    }
    private void setNews(String version,String notes){fullNews=notes;newsVersion.setText("VERSÃO "+version);StringBuilder summary=new StringBuilder();int count=0;for(String line:notes.split("[\\r\\n]+")){line=line.trim().replaceFirst("^[-*• ]+","");if(line.isEmpty())continue;if(count++==3)break;if(summary.length()>0)summary.append("\n\n");summary.append("• ").append(line);}news.setText(summary.toString());}
    private void showNews(){ScrollView scroll=new ScrollView(this);TextView body=new TextView(this);body.setText(fullNews);body.setTextSize(16);body.setTextColor(INK);body.setTextIsSelectable(true);body.setPadding(dp(20),dp(16),dp(20),dp(16));scroll.setBackgroundColor(CARD);scroll.addView(body);new AlertDialog.Builder(this).setTitle(newsVersion.getText()).setView(scroll).setPositiveButton("Fechar",null).show();}
    private void settings(){
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(1);panel.setPadding(24,12,24,12);
        TextView vl=new TextView(this);vl.setText("Volume do jogo");panel.addView(vl);SeekBar volume=new SeekBar(this);volume.setMax(100);volume.setProgress(prefs().getInt("volume",80));panel.addView(volume);
        Spinner display=new Spinner(this);display.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Manter proporção","Preencher tela","Tamanho original"}));display.setSelection(getSharedPreferences("mkxpz_prefs",0).getInt("display_mode",0));panel.addView(display);
        TextView al=new TextView(this);al.setText("Área do jogo (50–100%)");panel.addView(al);SeekBar area=new SeekBar(this);area.setMax(50);area.setProgress(Math.max(0,getSharedPreferences("mkxpz_prefs",0).getInt("game_area_scale",100)-50));panel.addView(area);
        Switch virtual=new Switch(this);virtual.setText("Controles na tela");virtual.setChecked(getSharedPreferences("mkxpz_prefs",0).getBoolean("touch_controls_enabled",true));panel.addView(virtual);
        Switch hide=new Switch(this);hide.setText("Ocultar ao conectar controle Bluetooth");hide.setChecked(getSharedPreferences("mkxpz_prefs",0).getBoolean("auto_hide_touch_controls",true));panel.addView(hide);
        EditText catalog=new EditText(this);catalog.setSingleLine(true);catalog.setHint("Endereço HTTPS do catálogo");catalog.setText(prefs().getString("catalog",ClientFiles.DEFAULT_CATALOG));panel.addView(catalog);
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);
        new AlertDialog.Builder(this).setTitle("Antes de jogar").setView(scroll).setPositiveButton("Salvar",(d,w)->{String url=catalog.getText().toString().trim();if(!url.startsWith("https://")){status.setText("O catálogo precisa usar HTTPS.");return;}prefs().edit().putInt("volume",volume.getProgress()).putString("catalog",url).apply();getSharedPreferences("mkxpz_prefs",0).edit().putInt("display_mode",display.getSelectedItemPosition()).putInt("game_area_scale",area.getProgress()+50).putBoolean("touch_controls_enabled",virtual.isChecked()).putBoolean("auto_hide_touch_controls",hide.isChecked()).apply();status.setText("Preferências salvas. O editor de botões e teste Bluetooth continuam disponíveis na engrenagem durante o jogo.");}).setNegativeButton("Voltar",null).show();
    }
    private void checkUpdates(boolean interactive){if(interactive&&inviteIfNeeded())return;final String requestedChannel=channel();Work operation=()->{
        JSONObject catalog;
        if(channel().equals("testers")){authorizeTester();if(testerRelease==null)throw new IOException("Convite ativo. Aguarde a publicação da versão de testes.");catalog=ClientFiles.verifyCatalog(testerRelease.getJSONObject("catalog").toString(),LauncherKeys.MODULUS);}
        else catalog=ClientFiles.catalog(prefs().getString("catalog",ClientFiles.DEFAULT_CATALOG),LauncherKeys.MODULUS);
        JSONObject channel=catalog.getJSONObject("channels").optJSONObject(channel());if(channel==null)throw new IOException("Ainda não existe versão publicada neste canal");
        JSONObject row=channel.optJSONObject("android");if(row==null)throw new IOException("Nenhuma atualização Android neste canal");
        int installed=0;try{installed=getPackageManager().getPackageInfo(selectedPackage(),0).versionCode;}catch(PackageManager.NameNotFoundException ignored){}
        boolean newer=row.getInt("code")>installed;String notes=row.optString("notes","Sem notas de versão");
        String compatibility="";JSONObject pc=channel.optJSONObject("windows");if(pc!=null&&!pc.optString("compatibility").equals(row.optString("compatibility")))compatibility="\nPC e Android publicados estão em versões online diferentes.";
        final String text=notes+compatibility;handler.post(()->{if(isFinishing()||gameRunning||!requestedChannel.equals(channel())||(!interactive&&busy))return;setNews(row.optString("version"),text);status.setText(newer?"Atualização disponível: "+row.optString("version"):"Aplicativo atualizado • "+row.optString("version"));if(interactive&&newer)new AlertDialog.Builder(this).setTitle("Atualizar aplicativo completo?").setMessage(text+"\nO Android pedirá sua confirmação para instalar. Seus saves serão mantidos.").setPositiveButton("Baixar",(d,w)->{
            Intent other=!channel().equals(ownChannel())?getPackageManager().getLaunchIntentForPackage(selectedPackage()):null;
            if(other!=null){other.putExtra("open_own_channel",true).putExtra("check_update",true);try{trustChannelPackage();if(channel().equals("testers"))other.putExtra("tester_credentials",testerCredentials().toString());startActivity(other);}catch(Exception error){status.setText("O aplicativo deste canal não tem a assinatura oficial. O convite foi preservado.");}}else downloadApk(row);
        }).setNegativeButton("Depois",null).show();});
    };if(interactive)work(operation);else new Thread(()->{try{operation.run();}catch(Exception error){handler.post(()->{if(!isFinishing()&&!busy&&!gameRunning)status.setText("Sem novidades disponíveis agora. Você pode jogar offline.");});}},"Nordeluna news check").start();}
    private void downloadApk(JSONObject row){
        if(busy)return;final java.util.concurrent.atomic.AtomicBoolean cancelled=new java.util.concurrent.atomic.AtomicBoolean();
        ProgressDialog dialog=new ProgressDialog(this);dialog.setTitle("Atualizando Nordeluna");dialog.setMessage("Baixando "+(row.optLong("size")/1024/1024)+" MB");dialog.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);dialog.setMax(100);dialog.setCancelable(false);dialog.setButton(ProgressDialog.BUTTON_NEGATIVE,"Cancelar",(d,w)->cancelled.set(true));dialog.show();
        work(()->{try{ClientFiles.backup(saves(),backups(),channel());File apk=ClientFiles.download(row,new File(getCacheDir(),"updates/Nordeluna.apk"),(text,percent)->{if(cancelled.get())throw new java.util.concurrent.CancellationException("Download cancelado");showProgress(text,percent);handler.post(()->dialog.setProgress(percent));});
            if(channel().equals("testers")){authorizeTester();if(!row.optBoolean("encrypted")||testerRelease==null)throw new IOException("Use uma versão de testes protegida por convite");File plain=new File(getCacheDir(),"updates/Nordeluna-unlocked.apk");TesterAccess.unlock(apk,plain,row,testerRelease.getJSONObject("keys").getString("android"));if(!apk.delete()||!plain.renameTo(apk))throw new IOException("Não foi possível concluir o APK de testes");}
            verifyApk(apk);if(cancelled.get())throw new java.util.concurrent.CancellationException("Download cancelado");pendingApk=apk;handler.post(()->{dialog.dismiss();installApk();});}finally{handler.post(()->dialog.dismiss());}});
    }
    @SuppressWarnings("deprecation") private void verifyApk(File apk)throws Exception{
        PackageManager manager=getPackageManager();PackageInfo candidate=manager.getPackageArchiveInfo(apk.getAbsolutePath(),PackageManager.GET_SIGNATURES),current=manager.getPackageInfo(getPackageName(),PackageManager.GET_SIGNATURES);
        int installed=0;try{installed=manager.getPackageInfo(selectedPackage(),0).versionCode;}catch(PackageManager.NameNotFoundException ignored){}
        if(candidate==null||!selectedPackage().equals(candidate.packageName)||candidate.versionCode<=installed||candidate.signatures==null||current.signatures==null||!new HashSet<>(Arrays.asList(candidate.signatures)).equals(new HashSet<>(Arrays.asList(current.signatures))))throw new IOException("O APK não é uma atualização assinada deste canal");
    }
    private void installApk(){
        if(pendingApk==null)return;
        if(Build.VERSION.SDK_INT>=26&&!getPackageManager().canRequestPackageInstalls()){startActivityForResult(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName())),71);return;}
        Uri uri=Uri.parse("content://"+getPackageName()+".updates/Nordeluna.apk");
        Intent install=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);startActivity(install);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==71){if(Build.VERSION.SDK_INT<26||getPackageManager().canRequestPackageInstalls())installApk();else status.setText("Instalação não autorizada. Você pode permitir nas configurações e tentar novamente.");}if(request==72&&result==RESULT_OK&&data!=null){Uri to=data.getData();work(()->{try(OutputStream out=getContentResolver().openOutputStream(to);ZipOutputStream zip=new ZipOutputStream(out)){zip.putNextEntry(new ZipEntry("diagnostico.json"));zip.write(safeReport().toString(2).getBytes(StandardCharsets.UTF_8));zip.closeEntry();}CrashDiagnostics.acknowledge(this);handler.post(()->status.setText("Relatório salvo. Você pode compartilhá-lo pelo aplicativo Arquivos."));});}}
    private void showBackups(){
        if(!channel().equals(ownChannel())){status.setText("Abra o outro canal para gerenciar os backups dele.");return;}
        File[] files=backups().listFiles(f->f.getName().matches("save-.*\\.zip"));if(files==null||files.length==0){status.setText("Os últimos cinco backups aparecerão aqui após jogar.");return;}Arrays.sort(files,Comparator.comparing(File::getName).reversed());String[] rows=new String[files.length];for(int i=0;i<files.length;i++)rows[i]=ClientFiles.describeBackup(files[i]);
        new AlertDialog.Builder(this).setTitle("Restaurar • "+channel()).setItems(rows,(d,n)->new AlertDialog.Builder(this).setTitle("Restaurar este backup?").setMessage("O save atual será copiado antes de substituir os arquivos.").setPositiveButton("Restaurar",(dialog,w)->work(()->{ClientFiles.restore(files[n],saves(),backups(),channel());handler.post(()->status.setText("Backup restaurado com segurança."));})).setNegativeButton("Voltar",null).show()).setNegativeButton("Voltar",null).show();
    }
    private JSONObject safeReport()throws Exception{JSONObject obj=new JSONObject();obj.put("app",BuildConfig.VERSION_NAME);obj.put("android",Build.VERSION.RELEASE);obj.put("model",Build.MANUFACTURER+" "+Build.MODEL);obj.put("channel",channel());obj.put("previous_crash",CrashDiagnostics.hasUnseenReport(this));obj.put("time",new Date().toString());
        if(Build.VERSION.SDK_INT>=30){android.app.ActivityManager manager=(android.app.ActivityManager)getSystemService(ACTIVITY_SERVICE);JSONArray exits=new JSONArray();if(manager!=null)for(android.app.ApplicationExitInfo exit:manager.getHistoricalProcessExitReasons(null,0,5)){JSONObject row=new JSONObject();row.put("reason",exit.getReason());row.put("status",exit.getStatus());row.put("time",exit.getTimestamp());row.put("pss_kib",exit.getPss());exits.put(row);}obj.put("previous_exits",exits);}return obj;}
    private void diagnostics(){work(()->{String health="Sem resposta do servidor";long start=System.nanoTime();try{java.net.HttpURLConnection c=ClientFiles.connection("https://nordeluna-online.discloud.dev/health");JSONObject reply;try(InputStream in=c.getInputStream()){reply=new JSONObject(new String(ClientFiles.bounded(in,65536),StandardCharsets.UTF_8));}finally{c.disconnect();}health="Servidor "+reply.optString("version")+" • "+((System.nanoTime()-start)/1000000)+" ms";}catch(Exception ignored){}
        final String result="Cliente "+BuildConfig.VERSION_NAME+" • "+channel()+"\n"+health+"\nBatalhas e trocas exigem a mesma versão online e o mesmo canal em PC e Android.";
        handler.post(()->new AlertDialog.Builder(this).setTitle("Diagnóstico").setMessage(result).setPositiveButton("Exportar relatório",(d,w)->exportReport()).setNegativeButton("Voltar",null).show());
    });}
    private void exportReport(){startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"Nordeluna-diagnostico.zip"),72);}
}
