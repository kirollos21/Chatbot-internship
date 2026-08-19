/// The Palm Hills visual language.
///
/// Built on the deep red of the Palm Hills logo, carried by the warm limestone
/// and sand of the communities themselves and lifted with the gold of sunlight
/// on them. Surfaces are a warm off-white rather than pure grey-white, which is
/// what keeps the app feeling like Palm Hills and not like a stock Material
/// demo.
///
/// [brand] is the Palm Hills red, `#A80336`, paired with white: white type and
/// icons on the red, white cards on a barely-tinted page. Every other colour
/// here is derived from that red or sits deliberately beside it, and the tokens
/// are named for their *role* rather than their hue — so changing the brand
/// colour stays a one-line edit in this file and needs no changes anywhere
/// else.
///
/// Everything here is defined in code. No image assets and no downloaded fonts:
/// the app ships with two dependencies on purpose, and a resident on a weak
/// connection should never wait on a font before reading a rule. The palm motif
/// is drawn by [PalmMotifPainter] for the same reason.
library;

import 'package:flutter/material.dart';

/// Brand colours. Referenced through [Theme] almost everywhere — reach for
/// these directly only for the decorative pieces the colour scheme has no slot
/// for, such as the hero gradient.
abstract final class PalmHills {
  /// The Palm Hills red, as specified.
  static const brand = Color(0xFFA80336);

  /// The same red darkened, for brand-coloured text on white (where the pure
  /// brand is a shade light for comfortable reading at small sizes) and for the
  /// closing end of the hero gradient.
  static const brandDeep = Color(0xFF740225);

  /// A wash of the brand for icon chips and selected states. Never for text —
  /// nothing legible sits on 8% of anything.
  static const brandSoft = Color(0xFFFBEAEF);

  /// Sunlight on sand. The second accent, and the only one that competes with
  /// the brand red for attention — used sparingly.
  static const gold = Color(0xFFA8842F);
  static const goldSoft = Color(0xFFF7EFDC);

  /// Advisory, not alarming: the "unverified" and "needs your project" flags.
  /// Deliberately not red — red now means the brand, so an amber caution stays
  /// distinguishable from ordinary chrome.
  static const amber = Color(0xFF8A5A12);
  static const amberSoft = Color(0xFFF9EFD9);

  /// The page behind every card. Barely tinted towards the brand rather than a
  /// cold grey, so white cards still read as white against it.
  static const sand = Color(0xFFF7F5F6);
  static const sandDim = Color(0xFFF1EDEF);

  /// Hairline borders. Cards are separated by a line, not a shadow — flat and
  /// bright reads as cleaner in Egyptian daylight than a floating card.
  static const line = Color(0xFFE8E2E4);

  /// Warm near-black rather than neutral grey, so body text sits with the red
  /// instead of looking pasted on top of it.
  static const ink = Color(0xFF1F1418);
  static const inkSoft = Color(0xFF6A5C60);

  /// The hero gradient: the brand red into its darker shade. Both ends clear AA
  /// for white text, so the greeting stays legible wherever it falls.
  static const heroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [brand, Color(0xFF6C0221)],
  );

  static const radiusCard = 18.0;
  static const radiusControl = 14.0;
}

ThemeData buildPalmHillsTheme() {
  final scheme =
      ColorScheme.fromSeed(seedColor: PalmHills.brand).copyWith(
    primary: PalmHills.brand,
    onPrimary: Colors.white,
    primaryContainer: PalmHills.brandSoft,
    onPrimaryContainer: PalmHills.brandDeep,
    // A selected filter chip picks up the secondary container, so this has to
    // be the brand wash rather than the gold - otherwise the one selected chip
    // on a screen is the only yellow thing in a red and white app.
    secondary: PalmHills.brand,
    onSecondary: Colors.white,
    secondaryContainer: PalmHills.brandSoft,
    onSecondaryContainer: PalmHills.brandDeep,
    tertiary: PalmHills.amber,
    onTertiary: Colors.white,
    tertiaryContainer: PalmHills.amberSoft,
    onTertiaryContainer: const Color(0xFF4A3208),
    surface: Colors.white,
    onSurface: PalmHills.ink,
    onSurfaceVariant: PalmHills.inkSoft,
    surfaceContainerLowest: Colors.white,
    surfaceContainerLow: const Color(0xFFFCFAF5),
    surfaceContainer: PalmHills.sand,
    surfaceContainerHigh: PalmHills.sandDim,
    surfaceContainerHighest: const Color(0xFFEDE7DA),
    outline: const Color(0xFFB0A5A8),
    outlineVariant: PalmHills.line,
  );

  final base = ThemeData(useMaterial3: true, colorScheme: scheme);

  // Colour the text theme FIRST, then adjust metrics on top of the coloured
  // styles. Overriding a style wholesale with a bare `TextStyle` drops the
  // colour `apply` just set, and a title with no colour renders invisible
  // against a white card.
  final text = base.textTheme
      .apply(bodyColor: PalmHills.ink, displayColor: PalmHills.brandDeep);

  return base.copyWith(
    scaffoldBackgroundColor: PalmHills.sand,

    // The bar sits on the page rather than above it: no elevation, no tint, so
    // the warm background runs unbroken from the status bar to the content.
    appBarTheme: const AppBarTheme(
      backgroundColor: PalmHills.sand,
      surfaceTintColor: Colors.transparent,
      foregroundColor: PalmHills.brandDeep,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: PalmHills.brandDeep,
        fontSize: 22,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.2,
      ),
    ),

    cardTheme: CardThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusCard),
        side: const BorderSide(color: PalmHills.line),
      ),
    ),

    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      indicatorColor: PalmHills.brandSoft,
      elevation: 0,
      height: 70,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          size: 24,
          color: states.contains(WidgetState.selected)
              ? PalmHills.brand
              : PalmHills.inkSoft,
        ),
      ),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 12,
          fontWeight: states.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
          color: states.contains(WidgetState.selected)
              ? PalmHills.brandDeep
              : PalmHills.inkSoft,
        ),
      ),
    ),

    navigationRailTheme: const NavigationRailThemeData(
      backgroundColor: Colors.white,
      indicatorColor: PalmHills.brandSoft,
      selectedIconTheme: IconThemeData(color: PalmHills.brand),
      unselectedIconTheme: IconThemeData(color: PalmHills.inkSoft),
      selectedLabelTextStyle: TextStyle(
        color: PalmHills.brandDeep,
        fontWeight: FontWeight.w700,
      ),
      unselectedLabelTextStyle: TextStyle(color: PalmHills.inkSoft),
    ),

    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 50),
        padding: const EdgeInsets.symmetric(horizontal: 22),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        ),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(0, 48),
        side: const BorderSide(color: PalmHills.line),
        foregroundColor: PalmHills.brandDeep,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        ),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: PalmHills.brand,
        textStyle: const TextStyle(fontWeight: FontWeight.w600),
      ),
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      hintStyle: const TextStyle(color: PalmHills.inkSoft),
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        borderSide: const BorderSide(color: PalmHills.line),
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        borderSide: const BorderSide(color: PalmHills.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        borderSide: const BorderSide(color: PalmHills.brand, width: 1.6),
      ),
      labelStyle: const TextStyle(color: PalmHills.inkSoft),
      floatingLabelStyle: const TextStyle(color: PalmHills.brand),
    ),

    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      side: const BorderSide(color: PalmHills.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      labelStyle: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: PalmHills.brandDeep,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
    ),

    dividerTheme: const DividerThemeData(
      color: PalmHills.line,
      thickness: 1,
      space: 1,
    ),

    listTileTheme: ListTileThemeData(
      iconColor: PalmHills.brand,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusCard),
      ),
    ),

    dialogTheme: DialogThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      titleTextStyle: const TextStyle(
        color: PalmHills.brandDeep,
        fontSize: 19,
        fontWeight: FontWeight.w700,
      ),
    ),

    snackBarTheme: SnackBarThemeData(
      backgroundColor: PalmHills.brandDeep,
      contentTextStyle: const TextStyle(color: Colors.white),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
      ),
    ),

    progressIndicatorTheme:
        const ProgressIndicatorThemeData(color: PalmHills.brand),

    popupMenuTheme: PopupMenuThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        side: const BorderSide(color: PalmHills.line),
      ),
    ),

    // Slightly looser lines than Material's default: Arabic sits taller than
    // Latin, and the two languages share these styles.
    textTheme: text.copyWith(
      headlineSmall: text.headlineSmall?.copyWith(
        fontSize: 26,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.4,
        height: 1.25,
      ),
      titleLarge: text.titleLarge?.copyWith(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.2,
        height: 1.3,
      ),
      titleMedium: text.titleMedium?.copyWith(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        height: 1.35,
      ),
      titleSmall: text.titleSmall?.copyWith(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.4,
      ),
      bodyLarge: text.bodyLarge?.copyWith(fontSize: 16, height: 1.5),
      bodyMedium: text.bodyMedium?.copyWith(fontSize: 14.5, height: 1.5),
      bodySmall: text.bodySmall?.copyWith(
        fontSize: 13,
        height: 1.45,
        color: PalmHills.inkSoft,
      ),
      labelSmall: text.labelSmall?.copyWith(
        fontSize: 11.5,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.6,
        color: PalmHills.inkSoft,
      ),
    ),
  );
}
