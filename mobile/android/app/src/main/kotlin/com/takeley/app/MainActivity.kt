package com.takeley.app

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "takeley/share")
            .setMethodCallHandler { call, result ->
                if (call.method != "share") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val text = call.argument<String>("text")
                val url = call.argument<String>("url")
                val title = call.argument<String>("title")
                if (text.isNullOrEmpty() || url.isNullOrEmpty()) {
                    result.error("error", "text and url required", null)
                    return@setMethodCallHandler
                }
                val uri = Uri.parse(url)
                val send = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_TEXT, text)
                    if (!title.isNullOrBlank()) {
                        putExtra(Intent.EXTRA_SUBJECT, title)
                        putExtra(Intent.EXTRA_TITLE, title)
                    }
                    clipData = ClipData.newRawUri(title ?: "TAKELEY", uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                startActivity(Intent.createChooser(send, title))
                result.success("unavailable")
            }
    }
}
