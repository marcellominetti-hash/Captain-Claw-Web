import 'dart:async';
import 'dart:io';

import 'package:dart_cast/dart_cast.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const FlowCastProbeApp());
}

class FlowCastProbeApp extends StatelessWidget {
  const FlowCastProbeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FlowCast Probe',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorSchemeSeed: Colors.deepPurple,
      ),
      home: const ProbePage(),
    );
  }
}

class ProbePage extends StatefulWidget {
  const ProbePage({super.key});

  @override
  State<ProbePage> createState() => _ProbePageState();
}

class _ProbePageState extends State<ProbePage> {
  static const MethodChannel _multicast = MethodChannel('flowcast/multicast');

  static const String _testMp4 =
      'https://storage.googleapis.com/cpe-sample-media/content/big_buck_bunny/prog/big_buck_bunny_prog.mp4';
  static const String _testHls =
      'https://storage.googleapis.com/cpe-sample-media/content/big_buck_bunny/big_buck_bunny_m4s_master.m3u8';

  late final CastService _service;
  StreamSubscription<List<CastDevice>>? _discoverySubscription;
  StreamSubscription<dynamic>? _stateSubscription;
  Timer? _reconnectTimer;

  final List<String> _log = <String>[];
  List<CastDevice> _devices = <CastDevice>[];
  CastSession? _session;
  CastDevice? _selectedDevice;
  bool _scanning = false;
  bool _connecting = false;
  bool _probing = false;
  int _reconnectAttempt = 0;

  bool get _isConnected => _session != null;

  @override
  void initState() {
    super.initState();
    _service = CastService(
      discoveryProviders: <DeviceDiscoveryProvider>[
        ChromecastDiscoveryProvider(),
      ],
      sessionFactory: (CastDevice device) {
        if (device.protocol != CastProtocol.chromecast) {
          throw UnsupportedError('Only Chromecast is enabled in this probe.');
        }
        return ChromecastSession(device: device);
      },
    );
    _addLog('Ready. Put phone and Mi Box on the same network, then press Scan.');
  }

  void _addLog(String message) {
    final String time = DateTime.now().toLocal().toIso8601String().substring(11, 19);
    if (!mounted) return;
    setState(() {
      _log.add('$time  $message');
    });
  }

  Future<void> _startScan() async {
    if (_scanning) return;

    await _discoverySubscription?.cancel();
    setState(() {
      _devices = <CastDevice>[];
      _scanning = true;
    });
    _addLog('Starting Chromecast discovery...');

    try {
      await _multicast.invokeMethod<void>('acquire');
      _addLog('Wi-Fi multicast lock acquired.');
    } catch (error) {
      _addLog('Multicast lock warning: $error');
    }

    try {
      _discoverySubscription = _service.startDiscovery().listen(
        (List<CastDevice> devices) {
          final List<CastDevice> chromecasts = devices
              .where((CastDevice d) => d.protocol == CastProtocol.chromecast)
              .toList(growable: false);
          if (!mounted) return;
          setState(() {
            _devices = chromecasts;
          });
          _addLog('Discovery update: ${chromecasts.length} device(s).');
        },
        onError: (Object error, StackTrace stackTrace) {
          _addLog('DISCOVERY ERROR: $error');
          if (mounted) setState(() => _scanning = false);
        },
      );

      await Future<void>.delayed(const Duration(seconds: 15));
      if (mounted) {
        setState(() => _scanning = false);
        _addLog('15 s checkpoint: ${_devices.length} Chromecast device(s) visible.');
      }
    } catch (error) {
      _addLog('DISCOVERY START ERROR: $error');
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<bool> _probeTcp(CastDevice device, int port) async {
    final Stopwatch sw = Stopwatch()..start();
    Socket? socket;
    try {
      socket = await Socket.connect(
        device.address,
        port,
        timeout: const Duration(seconds: 3),
      );
      sw.stop();
      _addLog('TCP $port OPEN (${sw.elapsedMilliseconds} ms).');
      return true;
    } on SocketException catch (error) {
      sw.stop();
      _addLog('TCP $port FAILED (${sw.elapsedMilliseconds} ms): ${error.message}.');
      return false;
    } catch (error) {
      sw.stop();
      _addLog('TCP $port ERROR (${sw.elapsedMilliseconds} ms): $error');
      return false;
    } finally {
      socket?.destroy();
    }
  }

  Future<bool> _runNetworkPreflight(CastDevice device) async {
    if (_probing) return false;
    setState(() => _probing = true);
    _addLog('Network preflight for ${device.name} (${device.address.address})...');

    try {
      final bool port8008 = await _probeTcp(device, 8008);
      final bool port8009 = await _probeTcp(device, 8009);

      if (port8008 && port8009) {
        _addLog('PREFLIGHT: 8008 + 8009 reachable. Proceeding to Cast TLS handshake.');
      } else if (port8008 && !port8009) {
        _addLog('PREFLIGHT: device HTTP is reachable but CastV2 :8009 is not. Receiver service may be stuck.');
      } else if (!port8008 && !port8009) {
        _addLog('PREFLIGHT: mDNS found the box but unicast TCP cannot reach it. Suspect hotspot/AP isolation or routing.');
      } else {
        _addLog('PREFLIGHT: :8009 reachable while :8008 is closed. Cast may still work; continuing.');
      }
      return port8009;
    } finally {
      if (mounted) setState(() => _probing = false);
    }
  }

  Future<void> _attachSession(CastDevice device, CastSession session) async {
    await _stateSubscription?.cancel();
    _session = session;
    _selectedDevice = device;
    _reconnectAttempt = 0;

    _stateSubscription = session.stateStream.listen((dynamic state) {
      final String text = state.toString();
      _addLog('SESSION STATE: $text');

      if (text.toLowerCase().contains('disconnected')) {
        if (_session == session) {
          _session = null;
          if (mounted) setState(() {});
        }
        _scheduleAutoReconnect(device);
      }
    });

    if (mounted) setState(() {});
  }

  Future<void> _connect(
    CastDevice device, {
    bool automatic = false,
    bool skipPreflight = false,
  }) async {
    if (_connecting) return;
    setState(() {
      _connecting = true;
      _selectedDevice = device;
    });

    _addLog(
      automatic
          ? 'Auto-reconnect attempt ${_reconnectAttempt + 1} to ${device.name}...'
          : 'Connecting to ${device.name} at ${device.address}:${device.port}...',
    );

    try {
      if (!skipPreflight) {
        final bool castPortOpen = await _runNetworkPreflight(device);
        if (!castPortOpen) {
          _addLog('CAST CONNECT SKIPPED: TCP :8009 is unreachable right now.');
          return;
        }
      }

      final CastSession session = await _service.connect(device);
      await _attachSession(device, session);
      _addLog(automatic ? 'Auto-reconnect succeeded.' : 'Connected to ${device.name}.');
    } catch (error) {
      _addLog(automatic ? 'AUTO-RECONNECT ERROR: $error' : 'CONNECT ERROR: $error');
      if (automatic) {
        _scheduleAutoReconnect(device);
      }
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  void _scheduleAutoReconnect(CastDevice device) {
    if (!mounted || _session != null) return;
    if (_reconnectAttempt >= 3) {
      _addLog('Auto-reconnect stopped after 3 attempts. Tap Reconnect or Network test.');
      return;
    }

    _reconnectTimer?.cancel();
    _reconnectAttempt += 1;
    final Duration delay = Duration(seconds: _reconnectAttempt);
    _addLog('Control socket disconnected. Retrying in ${delay.inSeconds}s...');
    _reconnectTimer = Timer(delay, () {
      if (mounted && _session == null) {
        _connect(device, automatic: true);
      }
    });
  }

  Future<CastSession?> _ensureConnected() async {
    if (_session != null) return _session;

    final CastDevice? device = _selectedDevice ?? (_devices.isNotEmpty ? _devices.first : null);
    if (device == null) {
      _addLog('No Mi Box remembered. Scan and select it first.');
      return null;
    }

    _reconnectTimer?.cancel();
    _addLog('No live control session. Reconnecting before LOAD...');
    await _connect(device);
    return _session;
  }

  Future<void> _cast(String url, CastMediaType type, String title) async {
    final CastSession? session = await _ensureConnected();
    if (session == null) {
      _addLog('MEDIA LOAD ABORTED: could not reconnect.');
      return;
    }

    try {
      _addLog('Loading $title...');
      await session.loadMedia(
        CastMedia(
          url: url,
          type: type,
          title: title,
        ),
      );
      _addLog('LOAD accepted by sender stack. Check the TV.');
    } catch (error) {
      _addLog('MEDIA LOAD ERROR: $error');
      if (error.toString().toLowerCase().contains('not connected')) {
        _session = null;
        if (mounted) setState(() {});
      }
    }
  }

  Future<void> _disconnect() async {
    _reconnectTimer?.cancel();
    _reconnectAttempt = 3;

    final CastSession? session = _session;
    if (session != null) {
      try {
        await session.disconnect();
      } catch (_) {}
    }

    await _stateSubscription?.cancel();
    _stateSubscription = null;
    if (!mounted) return;
    setState(() {
      _session = null;
      _selectedDevice = null;
    });
    _addLog('Disconnected by user.');
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _discoverySubscription?.cancel();
    _stateSubscription?.cancel();
    _session?.disconnect();
    _service.dispose();
    _multicast.invokeMethod<void>('release').catchError((_) {});
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final CastDevice? selected = _selectedDevice;
    final bool connected = _isConnected;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FlowCast Probe v0.2.3'),
        actions: <Widget>[
          IconButton(
            tooltip: 'Clear log',
            onPressed: () => setState(_log.clear),
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            ListTile(
              leading: Icon(connected ? Icons.cast_connected : Icons.cast),
              title: Text(
                connected
                    ? 'Connected: ${selected?.name ?? 'Cast device'}'
                    : selected == null
                        ? 'No Cast session'
                        : 'Disconnected: ${selected.name}',
              ),
              subtitle: Text(
                selected == null
                    ? 'Search for Chromecast / Chromecast built-in'
                    : '${selected.address}:${selected.port}${connected ? '' : ' • diagnostics ready'}',
              ),
              trailing: selected == null
                  ? FilledButton.icon(
                      onPressed: _scanning ? null : _startScan,
                      icon: const Icon(Icons.search),
                      label: Text(_scanning ? 'Scanning…' : 'Scan'),
                    )
                  : connected
                      ? TextButton(
                          onPressed: _disconnect,
                          child: const Text('Disconnect'),
                        )
                      : FilledButton(
                          onPressed: (_connecting || _probing) ? null : () => _connect(selected),
                          child: Text(_connecting || _probing ? 'Testing…' : 'Reconnect'),
                        ),
            ),
            if (selected == null && _devices.isNotEmpty)
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 210),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _devices.length,
                  itemBuilder: (BuildContext context, int index) {
                    final CastDevice device = _devices[index];
                    return ListTile(
                      leading: const Icon(Icons.tv),
                      title: Text(device.name),
                      subtitle: Text('${device.address}:${device.port}'),
                      onTap: _connecting ? null : () => _connect(device),
                    );
                  },
                ),
              ),
            if (selected != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                child: Column(
                  children: <Widget>[
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _probing ? null : () => _runNetworkPreflight(selected),
                        icon: const Icon(Icons.lan_outlined),
                        label: Text(_probing ? 'Testing ports…' : 'Network test 8008/8009'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: <Widget>[
                        Expanded(
                          child: FilledButton(
                            onPressed: (_connecting || _probing)
                                ? null
                                : () => _cast(
                                      _testMp4,
                                      CastMediaType.mp4,
                                      'FlowCast MP4 test',
                                    ),
                            child: const Text('Test MP4'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: FilledButton.tonal(
                            onPressed: (_connecting || _probing)
                                ? null
                                : () => _cast(
                                      _testHls,
                                      CastMediaType.hls,
                                      'FlowCast HLS test',
                                    ),
                            child: const Text('Test HLS'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            const Divider(height: 1),
            const Padding(
              padding: EdgeInsets.fromLTRB(12, 10, 12, 4),
              child: Row(
                children: <Widget>[
                  Icon(Icons.terminal, size: 18),
                  SizedBox(width: 8),
                  Text('Diagnostic log', style: TextStyle(fontWeight: FontWeight.bold)),
                ],
              ),
            ),
            Expanded(
              child: _log.isEmpty
                  ? const Center(child: Text('Press Scan to begin.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: _log.length,
                      itemBuilder: (BuildContext context, int index) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 5),
                          child: SelectableText(
                            _log[index],
                            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
