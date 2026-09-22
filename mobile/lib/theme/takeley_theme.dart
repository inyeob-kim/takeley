import 'package:flutter/material.dart';

import 'takeley_colors.dart';

/// Pretendard + Finimize-weighted type scale from design-system.mdc.
ThemeData buildTakeleyTheme() {
  const fontFamily = 'Pretendard';
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    fontFamily: fontFamily,
  ).textTheme;

  final textTheme = base
      .apply(
        bodyColor: TakeleyColors.fg,
        displayColor: TakeleyColors.fg,
        fontFamily: fontFamily,
      )
      .copyWith(
        // Screen / greeting title — 26–30 Bold, tracking ≈ -0.02em
        headlineMedium: base.headlineMedium?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w800,
          fontSize: 28,
          letterSpacing: -0.56,
          height: 1.25,
          color: TakeleyColors.fg,
        ),
        // Issue headline detail — 28–32 ExtraBold
        headlineLarge: base.headlineLarge?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w800,
          fontSize: 30,
          letterSpacing: -0.5,
          height: 1.25,
          color: TakeleyColors.fg,
        ),
        // Issue headline feed — 22–26 Bold
        titleLarge: base.titleLarge?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w700,
          fontSize: 24,
          height: 1.3,
          letterSpacing: -0.3,
          color: TakeleyColors.fg,
        ),
        // Section title — 17–18 SemiBold
        titleMedium: base.titleMedium?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w600,
          fontSize: 17,
          height: 1.35,
          color: TakeleyColors.fg,
        ),
        // Body detail — 16–17 Regular
        bodyLarge: base.bodyLarge?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w400,
          fontSize: 16,
          height: 1.6,
          color: TakeleyColors.fg,
        ),
        // Dek / summary — 15–16 muted
        bodyMedium: base.bodyMedium?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w400,
          fontSize: 15,
          height: 1.5,
          color: TakeleyColors.muted,
        ),
        // Meta — 12–13
        bodySmall: base.bodySmall?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w400,
          fontSize: 13,
          height: 1.4,
          color: TakeleyColors.muted,
        ),
        // Category — 11–12 Bold Accent, tracking ≈ 0.06em
        labelLarge: base.labelLarge?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.72,
          fontSize: 11,
          height: 1.2,
          color: TakeleyColors.accent,
        ),
        // Tab label — 10–11
        labelSmall: base.labelSmall?.copyWith(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w500,
          fontSize: 11,
          height: 1.2,
        ),
      );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    fontFamily: fontFamily,
    scaffoldBackgroundColor: TakeleyColors.canvas,
    colorScheme: const ColorScheme.light(
      primary: TakeleyColors.accent,
      onPrimary: Colors.white,
      secondary: TakeleyColors.rising,
      surface: TakeleyColors.canvas,
      onSurface: TakeleyColors.fg,
      outline: TakeleyColors.border,
    ),
    textTheme: textTheme,
    appBarTheme: AppBarTheme(
      backgroundColor: TakeleyColors.canvas,
      foregroundColor: TakeleyColors.fg,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
      shape: const Border(
        bottom: BorderSide(color: TakeleyColors.border, width: 1),
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: TakeleyColors.hairline,
      thickness: 2,
      space: 0,
    ),
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor: TakeleyColors.canvas,
      selectedItemColor: TakeleyColors.accent,
      unselectedItemColor: TakeleyColors.muted,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
      selectedLabelStyle: textTheme.labelSmall?.copyWith(
        fontWeight: FontWeight.w600,
        fontSize: 11,
        color: TakeleyColors.accent,
      ),
      unselectedLabelStyle: textTheme.labelSmall?.copyWith(
        fontWeight: FontWeight.w500,
        fontSize: 11,
        color: TakeleyColors.muted,
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: TakeleyColors.soft,
      selectedColor: TakeleyColors.accentSoft,
      labelStyle: textTheme.bodyMedium?.copyWith(
        color: TakeleyColors.fg,
        fontSize: 14,
        fontWeight: FontWeight.w500,
      ),
      secondaryLabelStyle: textTheme.bodyMedium?.copyWith(
        color: TakeleyColors.accent,
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(999),
        side: const BorderSide(color: TakeleyColors.border),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: TakeleyColors.soft,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    ),
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: CupertinoPageTransitionsBuilder(),
        TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
        TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
        TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
        TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
      },
    ),
  );
}
