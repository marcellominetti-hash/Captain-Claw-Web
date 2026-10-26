import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const FlowReversePhoneApp());
}

class FlowReversePhoneApp extends StatelessWidget {
  const FlowReversePhoneApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(useMaterial3: true, brightness: Brightness.dark, colorSchemeSeed: Colors.deepPurple),
      home: const ReverseServerPage(),
    );
  }
}

class ReverseServerPage extends StatefulWidget {
  const ReverseServerPage({super.key});

  @override
  State<ReverseServerPage> createState() => _ReverseServerPageState();
}

class _ReverseServerPageState extends State<ReverseServerPage> {
  final List<String> _log = <String>[];
  ServerSocket? _server;
  Socket? _client;
  StreamSubscription<List<int>>? _clientSub;
  bool _starting = false;

  void _logLine(String text) {
    final t = DateTime.now().toIso8601String().substring(11, 19);
    if (!mounted) return;
    setState(() => _log.add('$t  $text'));
  }

  Future<void> _start() async {
    if (_server != null || _starting) return;
    setState(() => _starting = true);
    try {
      _server = await ServerSocket.bind(InternetAddress.anyIPv4, 8765, shared: true);
      _logLine('Listening on 0.0.0.0:8765. Keep this app open.');
      _logLine('Install/open FlowReceiver on the Mi Box. It will connect TO this phone.');
      _server!.listen((Socket socket) {
        _client?.destroy();
        _client = socket;
        _logLine('Mi Box connected from ${socket.remoteAddress.address}:${socket.remotePort}.');
        socket.write('WELCOME FLOWREVERSE\n');
        _clientSub?.cancel();
        _clientSub = socket.listen((bytes) {
          for (final line in const LineSplitter().convert(utf8.decode(bytes, allowMalformed: true))) {
            _logLine('RX: $line');
          }
        }, onDone: () {
          _logLine('Mi Box disconnected. Waiting for automatic reconnect...');
          if (mounted) setState(() => _client = null);
        }, onError: (e) {
          _logLine('Client error: $e');
          if (mounted) setState(() => _client = null);
        });
        setState(() {});
      });
    } catch (e) {
      _logLine('SERVER ERROR: $e');
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }

  void _send(String command) {
    final c = _client;
    if (c == null) {
      _logLine('No Mi Box connected yet.');
      return;
    }
    c.write('$command\n');
    _logLine('TX: $command');
  }

  @override
  void dispose() {
    _clientSub?.cancel();
    _client?.destroy();
    _server?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final connected = _client != null;
    return Scaffold(
      appBar: AppBar(title: const Text('FlowReverse Phone v0.1')),
      body: SafeArea(
        child: Column(children: [
          ListTile(
            leading: Icon(connected ? Icons.link : Icons.wifi_tethering),
            title: Text(connected ? 'Mi Box reverse link connected' : _server == null ? 'Server stopped' : 'Waiting for Mi Box'),
            subtitle: const Text('Hotspot-safe channel: Mi Box → phone on TCP 8765'),
            trailing: FilledButton(onPressed: _server == null && !_starting ? _start : null, child: Text(_starting ? 'Starting…' : 'Start')),
          ),
          if (_server != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(children: [
                Expanded(child: FilledButton(onPressed: connected ? () => _send('PING') : null, child: const Text('Ping TV'))),
                const SizedBox(width: 8),
                Expanded(child: FilledButton.tonal(onPressed: connected ? () => _send('SHOW:FlowReverse works') : null, child: const Text('Show message'))),
              ]),
            ),
          const Divider(height: 1),
          const Padding(padding: EdgeInsets.all(12), child: Row(children: [Icon(Icons.terminal, size: 18), SizedBox(width: 8), Text('Diagnostic log', style: TextStyle(fontWeight: FontWeight.bold))])),
          Expanded(child: ListView.builder(padding: const EdgeInsets.all(12), itemCount: _log.length, itemBuilder: (_, i) => Padding(padding: const EdgeInsets.only(bottom: 5), child: SelectableText(_log[i], style: const TextStyle(fontFamily: 'monospace', fontSize: 12))))),
        ]),
      ),
    );
  }
}
