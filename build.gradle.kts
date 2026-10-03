plugins {
    // AGP 8.7.x uses the explicit Kotlin Android plugin below. AGP 9.x
    // enables an integrated Kotlin plugin and conflicts with that marker.
    id("com.android.application") version "8.7.3" apply false
    // Kotlin 2.0.21: stable release compatible with AGP 8.7.3 / Gradle 8.9,
    // and supports the kotlin { compilerOptions { ... } } DSL used in
    // app/build.gradle.kts. Declared here (apply false) so :app can apply
    // the plugin by id without repeating the version.
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
}
