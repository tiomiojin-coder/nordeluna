package com.mkxpz.launcher;

import android.app.*;
import android.os.*;
import android.content.*;
import android.content.pm.*;
import android.net.Uri;
import android.provider.Settings;
import android.graphics.Color;
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
    private Spinner channels;private boolean busy;private File pendingApk;
    private final android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
    private android.content.SharedPreferences prefs(){return getSharedPreferences(PREFS,MODE_PRIVATE);}
    private String ownChannel(){return getPackageName().endsWith(".testers")?"testers":"stable";}
    private String channel(){return prefs().getString("channel",ownChannel());}
    private String selectedPackage(){return "com.tiomi.nordeluna"+(channel().equals("testers")?".testers":"");}
    private File state(){return new File(getFilesDir(),"client-launcher");}
    private File saves(){return new File(getFilesDir(),"player-data/"+channel());}
    private File backups(){return new File(getFilesDir(),"player-backups/"+channel());}
    private interface Work { void run() throws Exception; }
    @Override public void onCreate(Bundle state){
        setTheme(android.R.style.Theme_Material_NoActionBar);
        if(gameRunning){super.onCreate(state);startActivity(new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));finish();return;}
        if(getIntent().getBooleanExtra("open_own_channel",false))prefs().edit().putString("channel",ownChannel()).apply();
        super.onCreate(state);getWindow().setStatusBarColor(Color.rgb(12,20,35));getWindow().setNavigationBarColor(Color.rgb(12,20,35));
        ScrollView scroll=new ScrollView(this);content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(28,24,28,28);content.setBackgroundColor(Color.rgb(12,20,35));scroll.addView(content);setContentView(scroll);
        TextView title=label("POKÉMON NORDELUNA",26);title.setTextColor(Color.rgb(112,224,231));
        label("Seu jogo, suas aventuras",15);channels=new Spinner(this);channels.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Estável","Testers · saves separados"}));channels.setSelection(channel().equals("testers")?1:0);content.addView(channels);
        channels.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int position,long id){if(busy)return;prefs().edit().putString("channel",position==1?"testers":"stable").apply();}});
        news=label("Confira as novidades antes de jogar. Sem internet? Você pode continuar offline.",16);
        button("JOGAR",()->play());button("Atualizar e ver novidades",()->checkUpdates(true));
        button("Backups e restauração",()->showBackups());button("Tela, áudio e controles",()->settings());button("Diagnóstico e compatibilidade",()->diagnostics());
        status=label("Versão "+BuildConfig.VERSION_NAME+" • pronto para jogar",14);progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);content.addView(progress);
        CrashDiagnostics.install(this,()->handler.post(()->{if(!isFinishing()&&CrashDiagnostics.hasUnseenReport(this))new AlertDialog.Builder(this).setTitle("O jogo foi interrompido").setMessage("Existe um diagnóstico do fechamento anterior. Você pode exportar um resumo sem saves ou dados de login.").setPositiveButton("Exportar",(d,w)->exportReport()).setNegativeButton("Depois",null).show();}));
        checkUpdates(getIntent().getBooleanExtra("check_update",false));
    }
    private TextView label(String text,int size){TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(Color.rgb(231,240,251));v.setPadding(4,8,4,12);content.addView(v);return v;}
    private void button(String text,Runnable action){Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setMinHeight(56);b.setFocusable(true);b.setOnClickListener(v->{if(!busy)action.run();});content.addView(b,new LinearLayout.LayoutParams(-1,-2));}
    private void work(Work task){if(busy)return;busy=true;channels.setEnabled(false);new Thread(()->{try{task.run();}catch(Exception error){handler.post(()->status.setText("Não foi possível concluir: "+error.getMessage()));}finally{handler.post(()->{busy=false;channels.setEnabled(true);});}},"Nordeluna launcher").start();}
    private void showProgress(String text,int percent){handler.post(()->{status.setText(text+" • "+percent+"%");progress.setProgress(percent);});}
    private void play(){work(()->{
        if(!channel().equals(ownChannel())){Intent open=getPackageManager().getLaunchIntentForPackage(selectedPackage());if(open==null)throw new IOException("Use Atualizar para instalar este canal. Seus saves serão separados do aplicativo estável.");open.putExtra("open_own_channel",true);handler.post(()->startActivity(open));return;}
        migrateStable(this,gameFolder(this));saves().mkdirs();ClientFiles.backup(saves(),backups(),channel());
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
        android.content.SharedPreferences p=c.getSharedPreferences(PREFS,MODE_PRIVATE);migrateStable(c,game);String channel=c.getPackageName().endsWith(".testers")?"testers":"stable";
        File saves=new File(c.getFilesDir(),"player-data/"+channel);saves.mkdirs();JSONObject cfg=new JSONObject();cfg.put("channel",channel);cfg.put("save_root",saves.getAbsolutePath());cfg.put("volume",p.getInt("volume",80));
        ClientFiles.write(new File(game,".nordeluna-launcher.json"),cfg.toString().getBytes(StandardCharsets.UTF_8));
    }
    public static File selectedSaves(Context c){String ch=c.getPackageName().endsWith(".testers")?"testers":"stable";return new File(c.getFilesDir(),"player-data/"+ch);}
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
    private void checkUpdates(boolean interactive){final String requestedChannel=channel();Work operation=()->{
        JSONObject catalog=ClientFiles.catalog(prefs().getString("catalog",ClientFiles.DEFAULT_CATALOG),LauncherKeys.MODULUS);
        JSONObject channel=catalog.getJSONObject("channels").optJSONObject(channel());if(channel==null)throw new IOException("Ainda não existe versão publicada neste canal");
        JSONObject row=channel.optJSONObject("android");if(row==null)throw new IOException("Nenhuma atualização Android neste canal");
        int installed=0;try{installed=getPackageManager().getPackageInfo(selectedPackage(),0).versionCode;}catch(PackageManager.NameNotFoundException ignored){}
        boolean newer=row.getInt("code")>installed;String notes=row.optString("notes","Sem notas de versão");
        String compatibility="";JSONObject pc=channel.optJSONObject("windows");if(pc!=null&&!pc.optString("compatibility").equals(row.optString("compatibility")))compatibility="\nPC e Android publicados estão em versões online diferentes.";
        final String text=notes+compatibility;handler.post(()->{if(isFinishing()||gameRunning||!requestedChannel.equals(channel())||(!interactive&&busy))return;news.setText(text);status.setText(newer?"Atualização disponível: "+row.optString("version"):"Aplicativo atualizado • "+row.optString("version"));if(interactive&&newer)new AlertDialog.Builder(this).setTitle("Atualizar aplicativo completo?").setMessage(text+"\nO Android pedirá sua confirmação para instalar. Seus saves serão mantidos.").setPositiveButton("Baixar",(d,w)->{
            Intent other=!channel().equals(ownChannel())?getPackageManager().getLaunchIntentForPackage(selectedPackage()):null;
            if(other!=null){other.putExtra("open_own_channel",true).putExtra("check_update",true);startActivity(other);}else downloadApk(row);
        }).setNegativeButton("Depois",null).show();});
    };if(interactive)work(operation);else new Thread(()->{try{operation.run();}catch(Exception error){handler.post(()->{if(!isFinishing()&&!busy&&!gameRunning)status.setText("Sem novidades disponíveis agora. Você pode jogar offline.");});}},"Nordeluna news check").start();}
    private void downloadApk(JSONObject row){
        if(busy)return;final java.util.concurrent.atomic.AtomicBoolean cancelled=new java.util.concurrent.atomic.AtomicBoolean();
        ProgressDialog dialog=new ProgressDialog(this);dialog.setTitle("Atualizando Nordeluna");dialog.setMessage("Baixando "+(row.optLong("size")/1024/1024)+" MB");dialog.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);dialog.setMax(100);dialog.setCancelable(false);dialog.setButton(ProgressDialog.BUTTON_NEGATIVE,"Cancelar",(d,w)->cancelled.set(true));dialog.show();
        work(()->{try{ClientFiles.backup(saves(),backups(),channel());File apk=ClientFiles.download(row,new File(getCacheDir(),"updates/Nordeluna.apk"),(text,percent)->{if(cancelled.get())throw new java.util.concurrent.CancellationException("Download cancelado");showProgress(text,percent);handler.post(()->dialog.setProgress(percent));});verifyApk(apk);if(cancelled.get())throw new java.util.concurrent.CancellationException("Download cancelado");pendingApk=apk;handler.post(()->{dialog.dismiss();installApk();});}finally{handler.post(()->dialog.dismiss());}});
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
