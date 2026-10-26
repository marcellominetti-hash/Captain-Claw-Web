import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const FlowReceiverApp());
}

class FlowReceiverApp extends StatelessWidget {
  const FlowReceiverApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(useMaterial3: true, brightness: Brightness.dark, colorSchemeSeed: Colors.deepPurple),
      home: const ReceiverPage(),
    );
  }
}

class ReceiverPage extends StatefulWidget {
  const ReceiverPage({super.key});

  @override
  State<ReceiverPage> createState() => _ReceiverPageState();
}

class _ReceiverPageState extends State<ReceiverPage> {
  static const MethodChannel _network = MethodChannel('flowreceiver/network');
  final List<String> _log = <String>[];
  Socket? _socket;
  Timer? _retryTimer;
  StreamSubscription<List<int>>? _sub;
  String _gateway = 'unknown';
  String _status = 'Starting…';
  String _message = 'Waiting for phone';
  int _attempt = 0;

  @override
  void initState() {
    super.initState();
    unawaited(_bootstrap());
  }

  void _addLog(String text) {
    final t = DateTime.now().toIso8601String().substring(11, 19);
    if (!mounted) return;
    setState(() => _log.add('$t  $text'));
  }

  Future<void> _bootstrap() async {
    try {
      final gateway = await _network.invokeMethod<String>('gateway');
      _gateway = gateway ?? 'unknown';
      _addLog('Hotspot gateway detected: $_gateway');
    } catch (e) {
      _addLog('Gateway detection error: $e');
    }
    await _connect();
  }

  Future<void> _connect() async {
    if (_gateway == 'unknown' || _gateway.isEmpty) {
      _scheduleRetry();
      return;
    }
    _attempt += 1;
    setState(() => _status = 'Connecting to phone…');
    _addLog('Connect attempt $_attempt → $_gateway:8765');
    try {
      final socket = await Socket.connect(_gateway, 8765, timeout: const Duration(seconds: 4));
      _socket?.destroy();
      _socket = socket;
      _attempt = 0;
      setState(() {
        _status = 'Connected to hotspot phone';
        _message = 'FlowReceiver link active';
      });
      _addLog('Reverse link CONNECTED to phone.');
      socket.write('HELLO FLOWRECEIVER\n');
      await _sub?.cancel();
      _sub = socket.listen((bytes) {
        final text = utf8.decode(bytes, allowMalformed: true);
        for (final line in const LineSplitter().convert(text)) {
          _addLog('RX: $line');
          if (line == 'PING') {
            socket.write('PONG\n');
          } else if (line.startsWith('SHOW:')) {
            setState(() => _message = line.substring(5));
            socket.write('SHOWN\n');
          }
        }
      }, onDone: () {
        _addLog('Phone link closed. Reconnecting…');
        _socket = null;
        setState(() => _status = 'Disconnected; retrying');
        _scheduleRetry();
      }, onError: (e) {
        _addLog('Socket error: $e');
        _socket = null;
        setState(() => _status = 'Disconnected; retrying');
        _scheduleRetry();
      });
    } catch (e) {
      _addLog('Connect failed: $e');
      setState(() => _status = 'Phone unreachable; retrying');
      _scheduleRetry();
    }
  }

  void _scheduleRetry() {
    _retryTimer?.cancel();
    final seconds = _attempt < 3 ? 2 : 5;
    _retryTimer = Timer(Duration(seconds: seconds), _connect);
  }

  @override
  void dispose() {
    _retryTimer?.cancel();
    _sub?.cancel();
    _socket?.destroy();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('FlowReceiver TV v0.1')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(_status, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('Phone gateway: $_gateway:8765'),
            const SizedBox(height: 28),
            Center(child: Text(_message, textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium)),
            const SizedBox(height: 28),
            FilledButton.icon(onPressed: _socket == null ? _connect : null, icon: const Icon(Icons.refresh), label: const Text('Reconnect')),
            const SizedBox(height: 16),
            const Divider(),
            const Text('Diagnostic log', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Expanded(child: ListView.builder(itemCount: _log.length, itemBuilder: (_, i) => Padding(padding: const EdgeInsets.only(bottom: 5), child: SelectableText(_log[i], style: const TextStyle(fontFamily: 'monospace', fontSize: 12))))),
          ]),
        ),
      ),
    );
  }
}
