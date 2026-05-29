import sqlite3
import os

DB_PATH = "instance/gerenciamento.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Banco de dados não encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Verifica se a tabela objetos já existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='objetos'")
        if cursor.fetchone():
            print("A tabela 'objetos' já existe. Migração parece já ter sido feita ou está parcialmente feita.")
            # Continuar ou abortar? Vamos assumir que precisa continuar se quebrou no meio, ou abortar
            # Para simplificar, vou tentar as tabelas e ignorar erros de "já existe".

        print("Iniciando migração...")

        # 2. Criar a tabela `objetos`
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS objetos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                projeto_id INTEGER NOT NULL,
                nome VARCHAR(200) NOT NULL,
                descricao TEXT,
                data_limite DATE NOT NULL,
                responsavel_id INTEGER,
                fase_atual_id INTEGER,
                FOREIGN KEY(projeto_id) REFERENCES projetos(projeto_id),
                FOREIGN KEY(responsavel_id) REFERENCES funcionarios(id_func),
                FOREIGN KEY(fase_atual_id) REFERENCES fases(id_fase)
            )
        """)

        # 3. Ler dados da tabela `projetos` para criar um `objeto` genérico por projeto
        # Nota: atividade, fase_atual_id serão removidos depois de projetos
        # E se 'atividade' não existir (já apagada num migrate prévio)? Temos que verificar
        cursor.execute("PRAGMA table_info(projetos)")
        cols = [col[1] for col in cursor.fetchall()]
        
        has_atividade = 'atividade' in cols
        has_fase_atual = 'fase_atual_id' in cols

        if has_fase_atual:
            cursor.execute("SELECT projeto_id, atividade, data_limite, responsavel_id, fase_atual_id FROM projetos")
            projetos = cursor.fetchall()
            
            for p in projetos:
                p_id, atividade, data_limite, responsavel_id, fase_atual_id = p
                nome_objeto = atividade if atividade else "Objeto Único"
                
                # Inserir o objeto com ID amarrado ao projeto para facilitar o vínculo
                cursor.execute("""
                    INSERT INTO objetos (id, projeto_id, nome, data_limite, responsavel_id, fase_atual_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (p_id, p_id, nome_objeto, data_limite, responsavel_id, fase_atual_id))
        else:
            print("Aviso: A tabela projetos já não possui 'fase_atual_id'. Pulando extração de objetos.")

        # 4. Renomear tabela `projeto_fase` para `objeto_fase` e sua coluna `projeto_id`
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projeto_fase'")
        if cursor.fetchone():
            cursor.execute("ALTER TABLE projeto_fase RENAME TO objeto_fase")
            # Renomear a coluna (suportado em SQLite >= 3.25)
            try:
                cursor.execute("ALTER TABLE objeto_fase RENAME COLUMN projeto_id TO objeto_id")
            except sqlite3.OperationalError:
                print("Aviso: Falha ao renomear coluna projeto_id para objeto_id. Versão do SQLite pode ser muito antiga.")

        # 5. Renomear tabela `projeto_fase_funcionario` para `objeto_fase_funcionario`
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projeto_fase_funcionario'")
        if cursor.fetchone():
            cursor.execute("ALTER TABLE projeto_fase_funcionario RENAME TO objeto_fase_funcionario")
            try:
                cursor.execute("ALTER TABLE objeto_fase_funcionario RENAME COLUMN id_projeto_fase TO id_objeto_fase")
            except sqlite3.OperationalError:
                pass

        # 6. Adicionar coluna `objeto_id` em `comentarios` e migrar
        cursor.execute("PRAGMA table_info(comentarios)")
        com_cols = [col[1] for col in cursor.fetchall()]
        if 'objeto_id' not in com_cols:
            cursor.execute("ALTER TABLE comentarios ADD COLUMN objeto_id INTEGER REFERENCES objetos(id)")
            
            # Migrar comentários para os objetos recém-criados
            # Como projeto_id == objeto.id, copiamos diretamente
            cursor.execute("UPDATE comentarios SET objeto_id = projeto_id")

        # 7. Limpar a tabela `projetos` removendo `fase_atual_id` e `atividade`
        # SQLite exige recriar a tabela para remover colunas caso a versão seja antiga, 
        # mas SQLite >= 3.35.0 suporta ALTER TABLE DROP COLUMN
        if has_fase_atual:
            try:
                cursor.execute("ALTER TABLE projetos DROP COLUMN fase_atual_id")
                cursor.execute("ALTER TABLE projetos DROP COLUMN atividade")
            except sqlite3.OperationalError as e:
                print(f"Aviso: Não foi possível realizar o DROP COLUMN em 'projetos' via ALTER TABLE: {e}")
                print("Sua versão do SQLite pode não suportar isso. O banco manterá as colunas inativas.")

        conn.commit()
        print("Migração concluída com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
