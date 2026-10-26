import 'dart:async';

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

  final List<String> _log = <String>[];
  List<CastDevice> _devices = <CastDevice>[];
  CastSession? _session;
  CastDevice? _connectedDevice;
  bool _scanning = false;
  bool _connecting = false;

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
    _addLog('Ready. Put phone and Mi Box on the same Wi-Fi, then press Scan.');
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

  Future<void> _connect(CastDevice device) async {
    if (_connecting) return;
    setState(() => _connecting = true);
    _addLog('Connecting to ${device.name} at ${device.address}:${device.port}...');

    try {
      final CastSession session = await _service.connect(device);
      await _stateSubscription?.cancel();
      _session = session;
      _connectedDevice = device;
      _stateSubscription = session.stateStream.listen((dynamic state) {
        _addLog('SESSION STATE: $state');
      });
      _addLog('Connected to ${device.name}.');
    } catch (error) {
      _addLog('CONNECT ERROR: $error');
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  Future<void> _cast(String url, CastMediaType type, String title) async {
    final CastSession? session = _session;
    if (session == null) {
      _addLog('Connect to the Mi Box first.');
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
    }
  }

  Future<void> _disconnect() async {
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
      _connectedDevice = null;
    });
    _addLog('Disconnected.');
  }

  @override
  void dispose() {
    _discoverySubscription?.cancel();
    _stateSubscription?.cancel();
    _session?.disconnect();
    _service.dispose();
    _multicast.invokeMethod<void>('release').catchError((_) {});
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final CastDevice? connected = _connectedDevice;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FlowCast Probe v0.2.1'),
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
              leading: Icon(
                connected == null ? Icons.cast : Icons.cast_connected,
              ),
              title: Text(
                connected == null
                    ? 'No Cast session'
                    : 'Connected: ${connected.name}',
              ),
              subtitle: Text(
                connected == null
                    ? 'Search for Chromecast / Chromecast built-in'
                    : '${connected.address}:${connected.port}',
              ),
              trailing: connected == null
                  ? FilledButton.icon(
                      onPressed: _scanning ? null : _startScan,
                      icon: const Icon(Icons.search),
                      label: Text(_scanning ? 'Scanning…' : 'Scan'),
                    )
                  : TextButton(
                      onPressed: _disconnect,
                      child: const Text('Disconnect'),
                    ),
            ),
            if (connected == null && _devices.isNotEmpty)
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
            if (connected != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                child: Row(
                  children: <Widget>[
                    Expanded(
                      child: FilledButton(
                        onPressed: () => _cast(
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
                        onPressed: () => _cast(
                          _testHls,
                          CastMediaType.hls,
                          'FlowCast HLS test',
                        ),
                        child: const Text('Test HLS'),
                      ),
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
