package com.flowcast.flowcast_probe

import android.content.Context
import android.net.wifi.WifiManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "flowcast/multicast"
    private var multicastLock: WifiManager.MulticastLock? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            channelName
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "acquire" -> {
                    try {
                        val wifi = applicationContext
                            .getSystemService(Context.WIFI_SERVICE) as WifiManager

                        if (multicastLock?.isHeld != true) {
                            multicastLock = wifi.createMulticastLock("FlowCastDiscovery").apply {
                                setReferenceCounted(false)
                                acquire()
                            }
                        }
                        result.success(true)
                    } catch (t: Throwable) {
                        result.error("MULTICAST_LOCK", t.message, null)
                    }
                }

                "release" -> {
                    try {
                        if (multicastLock?.isHeld == true) {
                            multicastLock?.release()
                        }
                        multicastLock = null
                        result.success(true)
                    } catch (t: Throwable) {
                        result.error("MULTICAST_UNLOCK", t.message, null)
                    }
                }

                else -> result.notImplemented()
            }
        }
    }

    override fun onDestroy() {
        try {
            if (multicastLock?.isHeld == true) multicastLock?.release()
        } catch (_: Throwable) {
        }
        multicastLock = null
        super.onDestroy()
    }
}
