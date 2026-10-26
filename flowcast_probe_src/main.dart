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
  Timer? _healthTimer;

  final List<String> _log = <String>[];
  List<CastDevice> _devices = <CastDevice>[];
  CastDevice? _rememberedDevice;
  CastSession? _session;
  bool _scanning = false;
  bool _connecting = false;
  bool _recovering = false;
  bool _subnetScanning = false;
  bool _port8009Open = false;

  bool get _connected => _session != null;

  @override
  void initState() {
    super.initState();
    _service = CastService(
      discoveryProviders: <DeviceDiscoveryProvider>[
        ChromecastDiscoveryProvider(),
      ],
      sessionFactory: (CastDevice device) => ChromecastSession(device: device),
    );
    _addLog('Hotspot Mode v2 ready. Phone = hotspot + sender.');
    _addLog('Discovery strategy: mDNS first, direct hotspot subnet scan fallback.');
  }

  void _addLog(String message) {
    if (!mounted) return;
    final String time = DateTime.now().toIso8601String().substring(11, 19);
    setState(() => _log.add('$time  $message'));
  }

  Future<void> _acquireMulticast() async {
    try {
      await _multicast.invokeMethod<void>('acquire');
      _addLog('Wi-Fi multicast lock acquired.');
    } catch (e) {
      _addLog('Multicast lock warning: $e');
    }
  }

  Future<void> _startScan() async {
    if (_scanning || _subnetScanning) return;
    await _discoverySubscription?.cancel();
    setState(() {
      _scanning = true;
      _devices = <CastDevice>[];
    });

    _addLog('Starting Chromecast mDNS discovery...');
    await _acquireMulticast();

    _discoverySubscription = _service.startDiscovery().listen(
      (List<CastDevice> devices) {
        final List<CastDevice> chromecasts = devices
            .where((CastDevice d) => d.protocol == CastProtocol.chromecast)
            .toList(growable: false);
        if (!mounted) return;
        setState(() => _devices = chromecasts);
        if (chromecasts.isNotEmpty) {
          _rememberedDevice = chromecasts.first;
          _addLog(
            'mDNS FOUND ${chromecasts.first.name} at '
            '${chromecasts.first.address.address}:${chromecasts.first.port}.',
          );
        }
      },
      onError: (Object error, StackTrace stack) {
        _addLog('mDNS discovery error: $error');
      },
    );

    await Future<void>.delayed(const Duration(seconds: 6));
    if (!mounted) return;

    setState(() => _scanning = false);
    if (_rememberedDevice != null || _devices.isNotEmpty) {
      _addLog('mDNS success. Hotspot subnet scan not needed.');
      return;
    }

    _addLog('No mDNS result after 6 s. Switching to direct hotspot subnet scan.');
    await _scanHotspotSubnets();
  }

  bool _isPrivateIpv4(String ip) {
    final List<int>? p = _ipv4Parts(ip);
    if (p == null) return false;
    if (p[0] == 10) return true;
    if (p[0] == 192 && p[1] == 168) return true;
    if (p[0] == 172 && p[1] >= 16 && p[1] <= 31) return true;
    return false;
  }

  List<int>? _ipv4Parts(String ip) {
    final List<String> raw = ip.split('.');
    if (raw.length != 4) return null;
    final List<int> out = <int>[];
    for (final String s in raw) {
      final int? v = int.tryParse(s);
      if (v == null || v < 0 || v > 255) return null;
      out.add(v);
    }
    return out;
  }

  Future<List<String>> _privateLocalIpv4s() async {
    final List<NetworkInterface> interfaces = await NetworkInterface.list(
      type: InternetAddressType.IPv4,
      includeLoopback: false,
    );
    final Set<String> addresses = <String>{};
    for (final NetworkInterface iface in interfaces) {
      for (final InternetAddress address in iface.addresses) {
        if (_isPrivateIpv4(address.address)) {
          addresses.add(address.address);
        }
      }
    }
    return addresses.toList(growable: false);
  }

  Future<bool> _quickPort(String ip, int port) async {
    Socket? socket;
    try {
      socket = await Socket.connect(
        ip,
        port,
        timeout: const Duration(milliseconds: 320),
      );
      return true;
    } catch (_) {
      return false;
    } finally {
      socket?.destroy();
    }
  }

  Future<CastDevice?> _scanOneSubnet(
    String base,
    Set<String> localAddresses,
  ) async {
    _addLog('Scanning $base.0/24 for Chromecast ports 8008/8009...');

    const int batchSize = 36;
    for (int start = 2; start <= 254; start += batchSize) {
      final int end = (start + batchSize - 1).clamp(2, 254);
      final List<String> ips = <String>[
        for (int host = start; host <= end; host++) '$base.$host',
      ].where((String ip) => !localAddresses.contains(ip)).toList();

      final List<MapEntry<String, List<bool>>> results =
          await Future.wait<MapEntry<String, List<bool>>>(
        ips.map((String ip) async {
          final List<bool> ports = await Future.wait<bool>(<Future<bool>>[
            _quickPort(ip, 8009),
            _quickPort(ip, 8008),
          ]);
          return MapEntry<String, List<bool>>(ip, ports);
        }),
      );

      for (final MapEntry<String, List<bool>> entry in results) {
        final bool p8009 = entry.value[0];
        final bool p8008 = entry.value[1];
        if (p8009 || p8008) {
          _addLog(
            'HOTSPOT CLIENT FOUND ${entry.key}: '
            '8008=${p8008 ? 'OPEN' : 'closed'}, '
            '8009=${p8009 ? 'OPEN' : 'closed'}.',
          );
          return CastDevice(
            id: 'hotspot-${entry.key}',
            name: 'Mi Box (hotspot)',
            protocol: CastProtocol.chromecast,
            address: InternetAddress(entry.key),
            port: 8009,
            metadata: <String, String>{'source': 'subnet-scan'},
          );
        }
      }
    }
    return null;
  }

  Future<void> _scanHotspotSubnets() async {
    if (_subnetScanning) return;
    setState(() => _subnetScanning = true);

    try {
      final List<String> locals = await _privateLocalIpv4s();
      if (locals.isEmpty) {
        _addLog('No private IPv4 interface visible to the app.');
        return;
      }

      _addLog('Private local IPv4: ${locals.join(', ')}');
      final Set<String> bases = <String>{};
      for (final String ip in locals) {
        final List<int>? p = _ipv4Parts(ip);
        if (p != null) bases.add('${p[0]}.${p[1]}.${p[2]}');
      }

      final List<String> orderedBases = bases.toList()
        ..sort((String a, String b) {
          int score(String s) {
            if (s.startsWith('192.168.')) return 0;
            if (s.startsWith('172.')) return 1;
            return 2;
          }
          return score(a).compareTo(score(b));
        });

      final Set<String> localSet = locals.toSet();
      for (final String base in orderedBases.take(4)) {
        final CastDevice? found = await _scanOneSubnet(base, localSet);
        if (found != null) {
          _rememberedDevice = found;
          if (mounted) {
            setState(() {
              _devices = <CastDevice>[found];
              _port8009Open = false;
            });
          }
          _addLog('Cached ${found.address.address}:8009 without mDNS.');
          return;
        }
      }

      _addLog('Subnet scan finished: no 8008/8009 client found.');
    } finally {
      if (mounted) setState(() => _subnetScanning = false);
    }
  }

  Future<bool> _probePort(
    CastDevice device,
    int port, {
    Duration timeout = const Duration(milliseconds: 1500),
    bool log = true,
  }) async {
    final Stopwatch sw = Stopwatch()..start();
    Socket? socket;
    try {
      socket = await Socket.connect(device.address, port, timeout: timeout);
      sw.stop();
      if (log) _addLog('TCP $port OPEN (${sw.elapsedMilliseconds} ms).');
      return true;
    } on SocketException catch (e) {
      sw.stop();
      if (log) {
        _addLog(
          'TCP $port unavailable (${sw.elapsedMilliseconds} ms): ${e.message}.',
        );
      }
      return false;
    } finally {
      socket?.destroy();
    }
  }

  Future<bool> _waitForCastPort(
    CastDevice device, {
    int attempts = 12,
  }) async {
    for (int i = 1; i <= attempts; i++) {
      _addLog(
        'Hotspot probe $i/$attempts → ${device.address.address}:8009',
      );
      if (await _probePort(device, 8009)) {
        if (mounted) setState(() => _port8009Open = true);
        return true;
      }
      if (mounted) setState(() => _port8009Open = false);
      if (i < attempts) {
        await Future<void>.delayed(
          Duration(milliseconds: 600 + i * 180),
        );
      }
    }
    return false;
  }

  Future<void> _networkTest() async {
    final CastDevice? d =
        _rememberedDevice ?? (_devices.isNotEmpty ? _devices.first : null);
    if (d == null) {
      _addLog('No Mi Box cached. Run Find Mi Box first.');
      return;
    }

    _addLog('Hotspot network test for ${d.address.address}...');
    final bool p8008 = await _probePort(d, 8008);
    final bool p8009 = await _probePort(d, 8009);
    setState(() => _port8009Open = p8009);

    if (p8008 && p8009) {
      _addLog('RESULT: hotspot unicast path healthy.');
    } else if (p8008 && !p8009) {
      _addLog(
        'RESULT: Mi Box is reachable; Chromecast :8009 is sleeping/stuck.',
      );
    } else if (!p8008 && !p8009) {
      _addLog(
        'RESULT: client IP is known but hotspot unicast is currently blocked.',
      );
    } else {
      _addLog('RESULT: :8009 reachable; Cast can proceed.');
    }
  }

  Future<void> _attachSession(
    CastDevice device,
    CastSession session,
  ) async {
    await _stateSubscription?.cancel();
    _session = session;
    _rememberedDevice = device;
    _stateSubscription = session.stateStream.listen((dynamic state) {
      final String s = state.toString();
      _addLog('SESSION STATE: $s');
      if (s.toLowerCase().contains('disconnected')) {
        if (_session == session) {
          _session = null;
          if (mounted) setState(() {});
        }
        unawaited(_recoverControlChannel());
      }
    });
    if (mounted) setState(() {});
    _startHealthMonitor();
  }

  Future<bool> _connectRemembered({bool recovery = false}) async {
    if (_connecting) return false;
    final CastDevice? d =
        _rememberedDevice ?? (_devices.isNotEmpty ? _devices.first : null);
    if (d == null) {
      _addLog('No Mi Box cached. Find it first.');
      return false;
    }

    setState(() => _connecting = true);
    try {
      _addLog(
        recovery
            ? 'Hotspot recovery: waiting for Cast port...'
            : 'Preparing Cast connection to ${d.address.address}...',
      );

      if (!await _waitForCastPort(d)) {
        _addLog('CAST CONNECT DEFERRED: :8009 never became reachable.');
        return false;
      }

      _addLog('Port ready. Starting CastV2/TLS handshake...');
      final CastSession session = await _service.connect(d);
      await _attachSession(d, session);
      _addLog(
        recovery ? 'Hotspot recovery succeeded.' : 'Connected to ${d.name}.',
      );
      return true;
    } catch (e) {
      _addLog('CAST CONNECT ERROR: $e');
      _session = null;
      return false;
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  Future<void> _recoverControlChannel() async {
    if (_recovering || _session != null || !mounted) return;
    setState(() => _recovering = true);
    _addLog('Control channel lost. Hotspot recovery started.');
    try {
      for (int cycle = 1; cycle <= 5 && _session == null; cycle++) {
        _addLog('Recovery cycle $cycle/5.');
        if (await _connectRemembered(recovery: true)) break;
        await Future<void>.delayed(Duration(seconds: cycle));
      }
      if (_session == null) {
        _addLog(
          'Recovery paused. Cached Mi Box retained; next media command retries.',
        );
      }
    } finally {
      if (mounted) setState(() => _recovering = false);
    }
  }

  void _startHealthMonitor() {
    _healthTimer?.cancel();
    _healthTimer = Timer.periodic(const Duration(seconds: 12), (_) async {
      final CastDevice? d = _rememberedDevice;
      if (d == null || !mounted) return;
      final bool open = await _probePort(
        d,
        8009,
        timeout: const Duration(milliseconds: 900),
        log: false,
      );
      if (mounted) setState(() => _port8009Open = open);
      if (!open && _session != null) {
        _addLog('WATCHDOG: :8009 disappeared; control channel stale.');
        _session = null;
        if (mounted) setState(() {});
        unawaited(_recoverControlChannel());
      }
    });
  }

  Future<CastSession?> _ensureSession() async {
    if (_session != null) return _session;
    if (_rememberedDevice == null) {
      await _scanHotspotSubnets();
    }
    if (await _connectRemembered()) return _session;
    return null;
  }

  Future<void> _cast(
    String url,
    CastMediaType type,
    String title,
  ) async {
    final CastSession? s = await _ensureSession();
    if (s == null) {
      _addLog('MEDIA LOAD ABORTED: hotspot Cast channel unavailable.');
      return;
    }

    try {
      _addLog('Loading $title...');
      await s.loadMedia(CastMedia(url: url, type: type, title: title));
      _addLog('LOAD accepted. Check the TV.');
    } catch (e) {
      _addLog('MEDIA LOAD ERROR: $e');
      _session = null;
      if (mounted) setState(() {});
      unawaited(_recoverControlChannel());
    }
  }

  Future<void> _disconnect() async {
    _healthTimer?.cancel();
    final CastSession? s = _session;
    if (s != null) {
      try {
        await s.disconnect();
      } catch (_) {}
    }
    await _stateSubscription?.cancel();
    _stateSubscription = null;
    if (mounted) setState(() => _session = null);
    _addLog('Disconnected by user. Mi Box IP kept in memory.');
  }

  @override
  void dispose() {
    _healthTimer?.cancel();
    _discoverySubscription?.cancel();
    _stateSubscription?.cancel();
    _session?.disconnect();
    _service.dispose();
    _multicast.invokeMethod<void>('release').catchError((_) {});
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final CastDevice? d = _rememberedDevice;
    final bool busy = _scanning || _subnetScanning || _connecting || _recovering;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FlowCast Probe v0.2.5'),
        actions: <Widget>[
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Center(
              child: Chip(
                avatar: const Icon(Icons.wifi_tethering, size: 18),
                label: const Text('HOTSPOT'),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            ListTile(
              leading: Icon(_connected ? Icons.cast_connected : Icons.cast),
              title: Text(
                _connected
                    ? 'Connected: ${d?.name ?? 'Mi Box'}'
                    : d == null
                        ? 'No Mi Box cached'
                        : 'Cached: ${d.name}',
              ),
              subtitle: Text(
                d == null
                    ? 'mDNS + direct hotspot IP scan'
                    : '${d.address.address}:${d.port} • '
                        '8009 ${_port8009Open ? 'OPEN' : 'unknown/down'}',
              ),
              trailing: d == null
                  ? FilledButton(
                      onPressed: busy ? null : _startScan,
                      child: Text(
                        _subnetScanning
                            ? 'IP scan…'
                            : _scanning
                                ? 'mDNS…'
                                : 'Find Mi Box',
                      ),
                    )
                  : _connected
                      ? TextButton(
                          onPressed: _disconnect,
                          child: const Text('Disconnect'),
                        )
                      : FilledButton(
                          onPressed: busy ? null : _connectRemembered,
                          child: Text(
                            _connecting || _recovering
                                ? 'Recovering…'
                                : 'Connect',
                          ),
                        ),
            ),
            if (d == null && _subnetScanning)
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: LinearProgressIndicator(),
              ),
            if (d != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
                child: Column(
                  children: <Widget>[
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: busy ? null : _networkTest,
                        icon: const Icon(Icons.lan_outlined),
                        label: const Text('Hotspot network test'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: <Widget>[
                        Expanded(
                          child: FilledButton(
                            onPressed: busy
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
                            onPressed: busy
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
                  Text(
                    'Diagnostic log',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: _log.length,
                itemBuilder: (context, index) => Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: SelectableText(
                    _log[index],
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
