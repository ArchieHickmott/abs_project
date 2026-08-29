{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = with pkgs; [
    # Python
    python313Full

    # C / C++
    gcc
    gdb

    cmake
    ninja

    pkg-config
  
    boost
    nlohmann_json

    # Crow / Networking
    crow
    asio
    openssl
    zlib

    # Geospatial / GDAL stack
    gdal
    geos
    proj

    # Development utilities
    curl
    git

    valgrind

    httpie

    pgadmin #optional, this is a gui program feel free to comment
  ];

shellHook = ''
    # Don't let Nix's Python packages leak into the project venv.
    unset PYTHONPATH
    export PYTHONNOUSERSITE=1

    if [ ! -d .venv ]; then
      python -m venv .venv
    fi

    source .venv/bin/activate

    echo ""
    echo "Python:"
    python --version
    echo "Python executable:"
    which python

    echo ""
    echo "C++:"
    g++ --version | head -n 1

    echo ""
    echo "CMake:"
    cmake --version | head -n 1
  '';
}