package com.mkxpz.launcher;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

/** Grants the Android installer access to precisely one verified APK. */
public final class ClientUpdateProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private File apk(Uri uri)throws FileNotFoundException{
        if(!"/Nordeluna.apk".equals(uri.getPath())||uri.getQuery()!=null)throw new FileNotFoundException();
        File file=new File(getContext().getCacheDir(),"updates/Nordeluna.apk");if(!file.isFile())throw new FileNotFoundException();return file;
    }
    @Override public String getType(Uri uri){return "application/vnd.android.package-archive";}
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{if(!"r".equals(mode))throw new FileNotFoundException();return ParcelFileDescriptor.open(apk(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
        MatrixCursor cursor=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});try{File f=apk(uri);cursor.addRow(new Object[]{f.getName(),f.length()});}catch(FileNotFoundException ignored){}return cursor;
    }
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    @Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
