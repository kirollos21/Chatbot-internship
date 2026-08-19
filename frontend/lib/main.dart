import 'package:flutter/material.dart';

import 'core/app_state.dart';
import 'core/strings.dart';
import 'screens/assistant_screen.dart';
import 'screens/contacts_screen.dart';
import 'screens/facilities_screen.dart';
import 'screens/home_screen.dart';
import 'screens/policies_screen.dart';
import 'screens/report_screen.dart';
import 'screens/tickets_screen.dart';
import 'screens/violations_screen.dart';

void main() => runApp(const PalmHillsApp());

class PalmHillsApp extends StatefulWidget {
  const PalmHillsApp({super.key});

  @override
  State<PalmHillsApp> createState() => _PalmHillsAppState();
}

class _PalmHillsAppState extends State<PalmHillsApp> {
  final AppState _state = AppState();

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      state: _state,
      child: AnimatedBuilder(
        animation: _state,
        builder: (context, _) {
          return MaterialApp(
            title: 'Palm Hills Assistant',
            debugShowCheckedModeBanner: false,
            theme: _buildTheme(),
            // Arabic must lay out right-to-left. Franco is Latin script, so it
            // stays LTR even though the language is Arabic.
            builder: (context, child) => Directionality(
              textDirection: _state.textDirection,
              child: child!,
            ),
            home: const RootShell(),
          );
        },
      ),
    );
  }

  ThemeData _buildTheme() {
    const seed = Color(0xFF1B5E4A);
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: seed),
      appBarTheme: const AppBarTheme(centerTitle: false),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: Colors.black.withValues(alpha: 0.08)),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
      ),
    );
  }
}

class RootShell extends StatefulWidget {
  const RootShell({super.key});

  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;

    final destinations = <_Destination>[
      _Destination(s.home, Icons.home_outlined, Icons.home, const HomeScreen()),
      _Destination(s.assistant, Icons.chat_bubble_outline, Icons.chat_bubble,
          const AssistantScreen()),
      _Destination(s.policies, Icons.menu_book_outlined, Icons.menu_book,
          const PoliciesScreen()),
      _Destination(s.violations, Icons.gavel_outlined, Icons.gavel,
          const ViolationsScreen()),
      _Destination(s.facilities, Icons.pool_outlined, Icons.pool,
          const FacilitiesScreen()),
      _Destination(s.contacts, Icons.call_outlined, Icons.call,
          const ContactsScreen()),
      _Destination(s.reportViolation, Icons.flag_outlined, Icons.flag,
          const ReportScreen()),
      _Destination(s.myRequests, Icons.receipt_long_outlined, Icons.receipt_long,
          const TicketsScreen()),
    ];

    final wide = MediaQuery.sizeOf(context).width >= 900;

    return Scaffold(
      appBar: AppBar(
        title: Text(destinations[_index].label),
        actions: const [LanguageMenu()],
      ),
      body: Row(
        children: [
          if (wide)
            NavigationRail(
              extended: MediaQuery.sizeOf(context).width >= 1200,
              selectedIndex: _index,
              onDestinationSelected: (i) => setState(() => _index = i),
              destinations: [
                for (final d in destinations)
                  NavigationRailDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.selectedIcon),
                    label: Text(d.label),
                  ),
              ],
            ),
          Expanded(child: destinations[_index].screen),
        ],
      ),
      bottomNavigationBar: wide
          ? null
          // Eight destinations do not fit a phone bottom bar; the four most
          // used stay there and the rest live on the Home screen grid.
          : NavigationBar(
              selectedIndex: _index.clamp(0, 3),
              onDestinationSelected: (i) => setState(() => _index = i),
              destinations: [
                for (final d in destinations.take(4))
                  NavigationDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.selectedIcon),
                    label: d.label,
                  ),
              ],
            ),
    );
  }
}

class _Destination {
  const _Destination(this.label, this.icon, this.selectedIcon, this.screen);
  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final Widget screen;
}

class LanguageMenu extends StatelessWidget {
  const LanguageMenu({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    return PopupMenuButton<AppLanguage>(
      icon: const Icon(Icons.language),
      tooltip: state.strings.languageLabel,
      initialValue: state.language,
      onSelected: state.setLanguage,
      itemBuilder: (context) => [
        for (final language in AppLanguage.values)
          PopupMenuItem(value: language, child: Text(language.label)),
      ],
    );
  }
}

/// Lets Home jump straight to a tab in the shell.
class ShellNavigator {
  static void goTo(BuildContext context, Widget screen, String title) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: Text(title), actions: const [LanguageMenu()]),
          body: screen,
        ),
      ),
    );
  }
}
