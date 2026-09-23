import 'package:flutter/cupertino.dart';

/// Pushes [page] with the same iOS slide used for Issue / Settings routes.
Future<T?> pushCupertinoPage<T extends Object?>(
  BuildContext context,
  Widget page,
) {
  return Navigator.of(context).push<T>(
    CupertinoPageRoute<T>(builder: (_) => page),
  );
}
