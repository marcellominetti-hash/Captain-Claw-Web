package com.flowreceiver.flowreceiver_tv

import android.content.Context
import android.net.wifi.WifiManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "flowreceiver/network"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "gateway" -> {
                        try {
                            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                            val gateway = wifi.dhcpInfo.gateway
                            val ip = String.format(
                                "%d.%d.%d.%d",
                                gateway and 0xff,
                                gateway shr 8 and 0xff,
                                gateway shr 16 and 0xff,
                                gateway shr 24 and 0xff
                            )
                            result.success(ip)
                        } catch (t: Throwable) {
                            result.error("GATEWAY_ERROR", t.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
